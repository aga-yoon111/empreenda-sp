// Improved frontend logic for EmpreendaSP (fetching server-side CSV through API)
const qs = s => document.querySelector(s)
const qsa = s => Array.from(document.querySelectorAll(s))

document.addEventListener('DOMContentLoaded', ()=>{
  const searchForm = qs('#search-form')
  const resultsDiv = qs('#results')
  const loadingEl = qs('#search-loading')
  const searchBtn = qs('#search-btn')
  const pcdCheckbox = qs('#pcd-mode')

  // Accessibility controls
  const incFont = qs('#increase-font')
  const decFont = qs('#decrease-font')
  const toggleContrast = qs('#toggle-contrast')

  incFont.addEventListener('click', ()=>{
    const cur = parseFloat(getComputedStyle(document.body).fontSize)
    document.body.style.fontSize = (cur + 1) + 'px'
  })
  decFont.addEventListener('click', ()=>{
    const cur = parseFloat(getComputedStyle(document.body).fontSize)
    document.body.style.fontSize = Math.max(12, cur - 1) + 'px'
  })
  toggleContrast.addEventListener('click', ()=>{
    document.body.classList.toggle('high-contrast')
  })

  // search form submit
  searchForm.addEventListener('submit', async (ev)=>{
    ev.preventDefault()
    resultsDiv.innerHTML = ''
    loadingEl.classList.remove('hidden')
    searchBtn.disabled = true

    const payload = {
      bairro: qs('#bairro').value || '',
      habilidades: qs('#habilidades').value || '',
      interesses: qs('#interesses').value || '',
      nao_gosta: qs('#nao_gosta').value || '',
      investimento: Number(qs('#investimento').value || 0),
      horas: Number(qs('#horas').value || 0),
      prioritario: qs('#prioritario').value || '',
      pcd_mode: pcdCheckbox.checked
    }

    try{
      const res = await fetch('/api/search', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify(payload)
      })
      if(!res.ok){
        const err = await res.json().catch(()=>({error:'Erro no servidor'}))
        throw new Error(err.error || 'Resposta inválida do servidor')
      }
      const data = await res.json()
      loadingEl.classList.add('hidden')
      searchBtn.disabled = false
      if(!data.results || data.results.length === 0){
        resultsDiv.innerHTML = '<div class="p-4 bg-yellow-50 rounded-md border border-yellow-200">Nenhuma sugestão encontrada. Tente ajustar os filtros.</div>'
        return
      }
      // render results
      data.results.forEach(r=>{
        const card = document.createElement('div')
        card.className = 'p-4 bg-white rounded-xl shadow-sm border'
        card.innerHTML = `
          <div class="flex items-start justify-between gap-3">
            <div>
              <h3 class="text-lg font-semibold text-blue-700">${r.nome}</h3>
              <p class="text-sm text-gray-600 mt-1">${r.descricao}</p>
            </div>
            <div class="text-right">
              <div class="text-sm text-gray-500">Score</div>
              <div class="text-xl font-bold text-blue-600">${Math.round((r.score||0)*100)}%</div>
            </div>
          </div>
          <div class="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm text-gray-700">
            <div><strong>Investimento:</strong> R$ ${Number(r.investimento_estimado||0).toLocaleString()}</div>
            <div><strong>Concorrência:</strong> ${r.concorrencia || '—'}</div>
            <div class="sm:col-span-2"><strong>Por que funciona no bairro:</strong> ${r.razao || 'Demanda local e baixo custo inicial.'}</div>
            <div class="sm:col-span-2 mt-2"><strong>7 passos (resumo):</strong> ${r.validacao_7_dias.slice(0,3).join(' • ')} <button class="ml-2 text-blue-600 underline btn-expand" data-id="${r.id}">Ver mais</button></div>
          </div>
          <div class="mt-3 flex items-center gap-2">
            <button class="px-3 py-2 bg-green-600 text-white rounded-md btn-check" data-name="${r.nome}"><i class="fas fa-check"></i> Verificar</button>
            <a class="ml-auto text-sm text-gray-500" href="${r.links_uteis && r.links_uteis[0] ? r.links_uteis[0].link : '#'}" target="_blank" rel="noopener">Contato útil</a>
          </div>
        `
        resultsDiv.appendChild(card)
      })

      // attach handlers
      qsa('.btn-check').forEach(b=>b.addEventListener('click', (e)=>{
        qs('#nome-negocio').value = e.currentTarget.dataset.name || ''
        // switch focus to evaluation form
        qs('#eval-bairro').focus()
        window.scrollTo({top: document.querySelector('#eval-form').offsetTop - 20, behavior:'smooth'})
      }))

      qsa('.btn-expand').forEach(btn=>{
        btn.addEventListener('click', (e)=>{
          const parent = btn.closest('.p-4')
          const idx = Array.from(resultsDiv.children).indexOf(parent)
          const item = data.results[idx]
          const detailHtml = `
            <div class="mt-2 text-sm text-gray-700">
              <strong>Validação 7 dias:</strong>
              <ol class="list-decimal list-inside ml-4 mt-1">${item.validacao_7_dias.map(s=>'<li>'+s+'</li>').join('')}</ol>
            </div>
          `
          // toggle detail
          const existing = parent.querySelector('.detail-expanded')
          if(existing){
            existing.remove()
            btn.textContent = 'Ver mais'
          } else {
            const d = document.createElement('div')
            d.className = 'detail-expanded mt-2'
            d.innerHTML = detailHtml
            parent.appendChild(d)
            btn.textContent = 'Fechar'
          }
        })
      })

    }catch(err){
      loadingEl.classList.add('hidden')
      searchBtn.disabled = false
      resultsDiv.innerHTML = `<div class="p-4 bg-red-50 text-red-700 rounded-md border border-red-200">Erro ao buscar: ${err.message}</div>`
      console.error('Erro em busca:', err)
    }
  })

  // Evaluation form
  qs('#eval-form').addEventListener('submit', async (ev)=>{
    ev.preventDefault()
    qs('#eval-result').innerHTML = ''
    qs('#eval-loading').classList.remove('hidden')
    const payload = {
      bairro: qs('#eval-bairro').value || '',
      nome_negocio: qs('#nome-negocio').value || '',
      habilidades: qs('#eval-habilidades').value || '',
      investimento: Number(qs('#eval-investimento').value || 0)
    }
    try{
      const res = await fetch('/api/evaluate', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)})
      if(!res.ok){
        const err = await res.json().catch(()=>({error:'Erro no servidor'}))
        throw new Error(err.error || 'Resposta inválida do servidor')
      }
      const data = await res.json()
      qs('#eval-loading').classList.add('hidden')
      // Render result
      let color = 'bg-red-50 text-red-700 border-red-200'
      if(data.evaluation === 'bom') color = 'bg-green-50 text-green-800 border-green-200'
      if(data.evaluation === 'risco') color = 'bg-yellow-50 text-yellow-800 border-yellow-200'
      qs('#eval-result').innerHTML = `<div class="p-4 rounded-md border ${color}">
        <div class="flex items-start gap-3">
          <div><strong>${(qs('#nome-negocio').value||'Negócio').toUpperCase()}</strong></div>
          <div class="ml-auto"><span class="text-sm">${data.evaluation.toUpperCase()}</span></div>
        </div>
        <ul class="mt-2 text-sm">${(data.reasons||[]).map(r=>'<li>'+r+'</li>').join('')}</ul>
        ${data.suggestions_button ? '<div class="mt-3"><button id="see-options" class="px-3 py-2 bg-blue-600 text-white rounded-md">Ver opções boas</button></div>' : ''}
      </div>`
      if(data.suggestions_button){
        qs('#see-options').addEventListener('click', ()=>{
          window.scrollTo({top:0,behavior:'smooth'})
        })
      }
    }catch(err){
      qs('#eval-loading').classList.add('hidden')
      qs('#eval-result').innerHTML = `<div class="p-3 bg-red-50 text-red-700 rounded-md border border-red-200">Erro ao avaliar: ${err.message}</div>`
      console.error('Erro avaliação:', err)
    }
  })

  // initial tiny accessibility state
  if(window.matchMedia && window.matchMedia('(prefers-contrast: more)').matches){
    document.body.classList.add('high-contrast')
  }
})
