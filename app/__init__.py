from flask import Flask, jsonify, request, send_from_directory, render_template
import csv, os, difflib, math, logging

logging.basicConfig(level=logging.INFO)
app = Flask(__name__, static_folder='static', template_folder='templates')

# CSV expected at data/businesses.csv (relative to project root)
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
DATA_CSV = os.path.join(PROJECT_ROOT, 'data', 'businesses.csv')

def load_data():
    rows = []
    if not os.path.exists(DATA_CSV):
        app.logger.error(f'CSV file not found: {DATA_CSV}')
        return rows
    try:
        with open(DATA_CSV, encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for r in reader:
                # Normalize numeric field
                try:
                    r['Investimento Estimado (R$)'] = float(r.get('Investimento Estimado (R$)', '').replace(',','') or 0)
                except:
                    r['Investimento Estimado (R$)'] = 0.0
                # Ensure keys exist and split list-like fields by semicolon
                for k in ['Habilidades Requeridas','Gostos/Interesses','Região-Alvo (Exemplos de Bairros)']:
                    raw = r.get(k,'') or ''
                    r[k] = [x.strip().lower() for x in raw.split(';') if x.strip()!='']
                rows.append(r)
    except Exception as e:
        app.logger.exception('Erro ao carregar CSV: %s', e)
    return rows

# Matching helpers
def fuzzy_skill_score(user_skills, required_skills):
    import difflib
    if not required_skills:
        return 0.0
    if not user_skills:
        return 0.0
    total = 0.0
    for req in required_skills:
        best = 0.0
        for u in user_skills:
            ratio = difflib.SequenceMatcher(None, req, u).ratio()
            if ratio > best: best = ratio
        total += best
    return total / len(required_skills)

def jaccard(a,b):
    if not a and not b: return 0.0
    A = set([x.lower() for x in a])
    B = set([x.lower() for x in b])
    inter = A.intersection(B)
    union = A.union(B)
    return len(inter) / len(union) if union else 0.0

def region_score(user_bairro, region_list):
    if not user_bairro: return 0.0
    ub = user_bairro.lower()
    if ub in region_list:
        return 1.0
    # nearby heuristic: same first token
    for r in region_list:
        if r.split()[0] == ub.split()[0]:
            return 0.5
    return 0.0

def investment_score(user_amount, estimated):
    if estimated <= 0: return 0.0
    try:
        user_amount = float(user_amount or 0)
    except:
        user_amount = 0.0
    if user_amount >= estimated:
        return 1.0
    return max(0.0, user_amount/estimated)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/search', methods=['POST'])
def api_search():
    try:
        data = request.get_json() or {}
        bairro = (data.get('bairro') or '').strip().lower()
        user_skills = [s.strip().lower() for s in (data.get('habilidades') or '').split(';') if s.strip()!='']
        user_interests = [s.strip().lower() for s in (data.get('interesses') or '').split(';') if s.strip()!='']
        investimento = float(data.get('investimento') or 0)
        pcd_mode = bool(data.get('pcd_mode', False))
        rows = load_data()
        results = []
        for r in rows:
            s_skill = fuzzy_skill_score(user_skills, r.get('Habilidades Requeridas', []))
            s_region = region_score(bairro, r.get('Região-Alvo (Exemplos de Bairros)', []))
            s_invest = investment_score(investimento, r.get('Investimento Estimado (R$)', 0))
            s_interest = jaccard(user_interests, r.get('Gostos/Interesses', []))
            score = 0.4*s_skill + 0.3*s_region + 0.2*s_invest + 0.1*s_interest
            pcd_boost = 0.0
            if pcd_mode:
                keywords = ['acessível','acesso','telefone','delivery','atendimento por telefone','logística acessível','adaptado']
                text = ' '.join([r.get('Descrição Detalhada',''), ' '.join(r.get('Região-Alvo (Exemplos de Bairros)',[]))]).lower()
                for kw in keywords:
                    if kw in text:
                        pcd_boost = 0.05
                        break
            final_score = min(1.0, score + pcd_boost)
            results.append({
                'id': r.get('ID'),
                'nome': r.get('Nome do Negócio'),
                'descricao': r.get('Descrição Detalhada'),
                'investimento_estimado': r.get('Investimento Estimado (R$)'),
                'concorrencia': r.get('Concorrência (SP)'),
                'regiao_alvo': r.get('Região-Alvo (Exemplos de Bairros)'),
                'razao': r.get('Razão para ser um Bom Negócio',''),
                'score_components': {
                    'habilidades': round(s_skill,3),
                    'regiao': round(s_region,3),
                    'investimento': round(s_invest,3),
                    'interesses': round(s_interest,3),
                    'pcd_boost': round(pcd_boost,3)
                },
                'score': round(final_score,3)
            })
        results_sorted = sorted(results, key=lambda x: x['score'], reverse=True)[:5]
        # add validation plan and links
        for r in results_sorted:
            r['validacao_7_dias'] = [
                "Dia 1: Conversar com 5 vizinhos/possíveis clientes.",
                "Dia 2: Criar amostra/protótipo do produto ou serviço.",
                "Dia 3: Teste de preço com oferta pequena.",
                "Dia 4: Verificar logística e fornecedores.",
                "Dia 5: Recolher feedback e ajustar.",
                "Dia 6: Anunciar em grupos locais/feiras.",
                "Dia 7: Buscar apoio no Sebrae/Casa do Empreendedor."
            ]
            r['links_uteis'] = [
                {'nome':'Sebrae-SP','link':'https://www.sebraesp.com.br'},
                {'nome':'Casa do Empreendedor','link':'https://www.prefeitura.sp.gov.br/casadosempreendedores'},
                {'nome':'Linha de apoio','link':'(11) 4000-0000'}
            ]
        return jsonify({'results': results_sorted})
    except Exception as e:
        app.logger.exception('Erro em /api/search: %s', e)
        return jsonify({'error':'Erro interno ao processar busca. Verifique o CSV e o servidor.'}), 500

@app.route('/api/evaluate', methods=['POST'])
def api_evaluate():
    try:
        data = request.get_json() or {}
        bairro = (data.get('bairro') or '').strip().lower()
        nome_negocio = (data.get('nome_negocio') or '').strip().lower()
        rows = load_data()
        # find best match by name
        import difflib
        best = None
        best_score = 0.0
        for r in rows:
            name = r.get('Nome do Negócio','').lower()
            ratio = difflib.SequenceMatcher(None, name, nome_negocio).ratio()
            if ratio > best_score:
                best_score = ratio
                best = r
        reasons = []
        evaluation = 'não recomendado'
        if best is None or best_score < 0.4:
            evaluation = 'não recomendado'
            reasons.append('Não encontramos um negócio parecido no banco de dados para avaliar.')
        else:
            user_skills = [s.strip().lower() for s in (data.get('habilidades') or '').split(';') if s.strip()!='']
            investimento = float(data.get('investimento') or 0)
            s_skill = fuzzy_skill_score(user_skills, best.get('Habilidades Requeridas', []))
            s_region = region_score(bairro, best.get('Região-Alvo (Exemplos de Bairros)', []))
            s_invest = investment_score(investimento, best.get('Investimento Estimado (R$)', 0))
            score = 0.4*s_skill + 0.3*s_region + 0.2*s_invest
            if score >= 0.7:
                evaluation = 'bom'
            elif score >= 0.45:
                evaluation = 'risco'
            else:
                evaluation = 'não recomendado'
            reasons.append(f"Similaridade com habilidades: {round(s_skill,2)}")
            reasons.append(f"Adequação à região: {round(s_region,2)}")
            reasons.append(f"Adequação ao investimento: {round(s_invest,2)}")
            reasons.append(f"Pontuação final: {round(score,2)} (bom>=0.7, risco>=0.45)")
        response = {
            'nome_avaliado': nome_negocio,
            'match_score': round(best_score,3),
            'evaluation': evaluation,
            'reasons': reasons,
            'suggestions_button': (evaluation != 'bom')
        }
        return jsonify(response)
    except Exception as e:
        app.logger.exception('Erro em /api/evaluate: %s', e)
        return jsonify({'error':'Erro interno ao avaliar. Verifique o CSV e o servidor.'}), 500

# Serve static files
@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(os.path.join(os.path.dirname(__file__),'static'), filename)
