from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, ClientConfig, Lead
from functools import wraps
from datetime import timedelta
import os
import toml
import urllib.parse
import requests
from facebook_service import get_active_campaigns, get_campaign_insights, get_account_insights_breakdown
from facebook_capi import send_event

app = Flask(__name__)

# Configuration - Production ready with environment variables
app.secret_key = os.environ.get('SECRET_KEY', 'super_secret_key_for_session')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///agencyos.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Session Configuration - Keep users logged in
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)  # Session lasts 30 days
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevent XSS attacks
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # CSRF protection
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=30)  # Remember me duration

# Load Gemini API Key from environment or secrets file
gemini_key = os.environ.get('GEMINI_API_KEY')
if not gemini_key:
    try:
        secrets = toml.load('.streamlit/secrets.toml')
        gemini_key = secrets.get('GEMINI_API_KEY', '')
    except FileNotFoundError:
        gemini_key = ''
        
app.config['GEMINI_API_KEY'] = gemini_key

# Initialize Extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- HELPERS ---

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role != role:
                # Allow Master to access Gestor routes, Gestor to access Lojista? 
                # For strict RBAC:
                if current_user.role == 'MASTER': pass # Master can do anything
                elif current_user.role == 'GESTOR' and role == 'LOJISTA': pass
                else:
                    flash("Acesso não autorizado.", "error")
                    return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def get_current_client_config():
    """Returns the ClientConfig for the currently selected client (Gestor view) or current user (Lojista view)."""
    if current_user.role == 'LOJISTA':
        # For lojista, get their own ClientConfig
        return ClientConfig.query.filter_by(user_id=current_user.id).first()
    elif current_user.role in ['GESTOR', 'MASTER']:
        # For gestor/master, get the active client's config
        active_client_id = session.get('active_client_id')
        if active_client_id:
            return ClientConfig.query.filter_by(user_id=active_client_id).first()
    return None

# --- ROUTES ---

@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'LOJISTA':
            return redirect(url_for('client_app_home'))
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            # Mark session as permanent (lasts 30 days)
            session.permanent = True
            # Login with remember me enabled
            login_user(user, remember=True)
            
            if user.role == 'MASTER':
                return redirect(url_for('users_list'))
            elif user.role == 'GESTOR':
                return redirect(url_for('dashboard'))
            else:  # LOJISTA
                return redirect(url_for('client_app_home'))
        else:
            flash("Usuário ou senha inválidos.", "error")
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- DASHBOARD (GESTOR) ---

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'LOJISTA':
        return redirect(url_for('client_app_home'))
    
    # MASTER gets administrative overview
    if current_user.role == 'MASTER':
        return redirect(url_for('admin_overview'))
    
    # GESTOR gets operational dashboard
    # Get Clients for Sidebar Selector
    clients = User.query.filter_by(role='LOJISTA', parent_id=current_user.id).all()
        
    active_client_id = session.get('active_client_id')
    active_client = User.query.get(active_client_id) if active_client_id else None
    
    # If no client selected, select the first one
    if not active_client and clients:
        active_client = clients[0]
        session['active_client_id'] = active_client.id
    
    # Date Filter
    date_preset = request.args.get('date_preset', 'maximum')
    
    # Fetch Real-Time Data from Facebook
    ad_spend = 0
    impressions = 0
    clicks = 0
    cpc = 0
    ctr = 0
    leads = []
    total_sales = 0
    total_revenue = 0
    
    # Breakdowns
    breakdown_data = {
        'age_gender': [],
        'platform': [],
        'region': []
    }
    
    if active_client:
        leads = Lead.query.filter_by(client_id=active_client.id).order_by(Lead.timestamp.desc()).all()
        total_sales = sum(1 for l in leads if l.status == 'SOLD')
        total_revenue = sum(l.sale_value for l in leads if l.sale_value)
        
        # Fetch Facebook Metrics
        conf = get_current_client_config()
        if conf and conf.fb_access_token and conf.ad_account_id:
            try:
                # 1. Aggregate Campaign Metrics
                campaigns = get_active_campaigns(conf.fb_access_token, conf.ad_account_id)
                for camp in campaigns:
                    insights = get_campaign_insights(conf.fb_access_token, camp['id'], date_preset=date_preset)
                    if insights:
                        data = insights[0]
                        ad_spend += float(data.get('spend', 0))
                        impressions += int(data.get('impressions', 0))
                        clicks += int(data.get('clicks', 0))
                
                # 2. Fetch Breakdowns
                breakdown_data = get_account_insights_breakdown(conf.fb_access_token, conf.ad_account_id, date_preset=date_preset)
                
            except Exception as e:
                print(f"Error fetching dashboard metrics: {e}")
                
    # Calculate Derived Metrics
    cpc = (ad_spend / clicks) if clicks > 0 else 0
    ctr = (clicks / impressions * 100) if impressions > 0 else 0
    roas = (total_revenue / ad_spend) if ad_spend > 0 else 0

    return render_template('dashboard_overview.html', 
                           clients=clients,
                           active_client=active_client,
                           leads=leads,
                           total_leads=len(leads),
                           total_sales=total_sales,
                           total_revenue=total_revenue,
                           ad_spend=ad_spend,
                           impressions=impressions,
                           clicks=clicks,
                           cpc=cpc,
                           ctr=ctr,
                           roas=roas,
                           breakdown_data=breakdown_data,
                           current_date_preset=date_preset)

@app.route('/dashboard/links')
@login_required
def link_generator():
    # Sidebar Context
    if current_user.role == 'MASTER':
        clients = User.query.filter_by(role='LOJISTA').all()
    else:
        clients = User.query.filter_by(role='LOJISTA', parent_id=current_user.id).all()
    active_client = User.query.get(session.get('active_client_id'))
    
    return render_template('link_generator.html', clients=clients, active_client=active_client)

@app.route('/dashboard/admin-overview')
@login_required
def admin_overview():
    if current_user.role != 'MASTER':
        return redirect(url_for('dashboard'))
    
    # Get all users with stats (administrative view)
    all_users = User.query.filter(User.id != current_user.id).order_by(User.id.desc()).all()
    
    user_stats = []
    total_lojistas = 0
    total_gestores = 0
    total_leads_system = 0
    total_sales_system = 0
    
    for user in all_users:
        if user.role == 'MASTER':
            continue
            
        stats = {
            'id': user.id,
            'username': user.username,
            'role': user.role,
            'leads_count': 0,
            'sales_count': 0,
            'revenue': 0,
            'has_config': False,
            'last_activity': 'N/A'
        }
        
        if user.role == 'LOJISTA':
            total_lojistas += 1
            leads = Lead.query.filter_by(client_id=user.id).all()
            stats['leads_count'] = len(leads)
            stats['sales_count'] = sum(1 for l in leads if l.status == 'SOLD')
            stats['revenue'] = sum(l.sale_value for l in leads if l.sale_value)
            
            total_leads_system += stats['leads_count']
            total_sales_system += stats['sales_count']
            
            conf = ClientConfig.query.filter_by(user_id=user.id).first()
            stats['has_config'] = bool(conf and conf.fb_access_token)
            
            if leads:
                last_lead = max(leads, key=lambda x: x.timestamp)
                stats['last_activity'] = last_lead.timestamp.strftime('%d/%m/%Y')
        elif user.role == 'GESTOR':
            total_gestores += 1
            # Count lojistas under this gestor
            lojistas = User.query.filter_by(parent_id=user.id, role='LOJISTA').all()
            stats['leads_count'] = sum(Lead.query.filter_by(client_id=l.id).count() for l in lojistas)
        
        user_stats.append(stats)
    
    return render_template('master_dashboard.html',
                         users=user_stats,
                         total_lojistas=total_lojistas,
                         total_gestores=total_gestores,
                         total_leads=total_leads_system,
                         total_sales=total_sales_system)

@app.route('/dashboard/select_client/<int:user_id>')
@login_required
def select_client(user_id):
    """Select active client for dashboard"""
    session['active_client_id'] = user_id
    return redirect(url_for('dashboard'))

# --- CLIENT MANAGEMENT (Multi-Tenant) ---

@app.route('/dashboard/clients')
@login_required
def clients_list():
    """List all clients for the current GESTOR"""
    if current_user.role == 'LOJISTA':
        return redirect(url_for('client_app_home'))
    
    # Get clients managed by this gestor
    if current_user.role == 'MASTER':
        clients = ClientConfig.query.all()
    else:
        clients = ClientConfig.query.filter_by(gestor_id=current_user.id).all()
    
    return render_template('clients.html', clients=clients)

@app.route('/dashboard/clients', methods=['POST'])
@login_required
def create_client():
    """Create a new client with independent credentials"""
    if current_user.role == 'LOJISTA':
        return jsonify({"success": False, "error": "Sem permissão"}), 403
    
    data = request.json
    
    # Validate required fields
    required = ['name', 'ad_account_id', 'pixel_id', 'access_token']
    for field in required:
        if not data.get(field):
            return jsonify({"success": False, "error": f"Campo '{field}' é obrigatório"}), 400
    
    # Create Lojista user for this client
    try:
        # Generate unique username from business name
        base_username = data['name'].lower().replace(' ', '_')
        username = base_username
        counter = 1
        while User.query.filter_by(username=username).first():
            username = f"{base_username}_{counter}"
            counter += 1
        
        # Create Lojista user
        lojista = User(
            username=username,
            password_hash=generate_password_hash('password123', method='pbkdf2:sha256'),  # Default password
            role='LOJISTA',
            parent_id=current_user.id
        )
        db.session.add(lojista)
        db.session.flush()  # Get the ID
        
        # Create ClientConfig with credentials
        client_config = ClientConfig(
            name=data['name'],
            fb_access_token=data['access_token'],
            ad_account_id=data['ad_account_id'],
            pixel_id=data['pixel_id'],
            whatsapp_number=data.get('whatsapp_number'),
            gestor_id=current_user.id,
            user_id=lojista.id
        )
        db.session.add(client_config)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": f"Cliente '{data['name']}' criado com sucesso!"
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/dashboard/clients/<int:client_id>', methods=['PUT'])
@login_required
def update_client(client_id):
    """Update client credentials"""
    if current_user.role == 'LOJISTA':
        return jsonify({"success": False, "error": "Sem permissão"}), 403
    
    client = ClientConfig.query.get(client_id)
    
    # Security: Only allow gestor to edit their own clients
    if not client or (client.gestor_id != current_user.id and current_user.role != 'MASTER'):
        return jsonify({"success": False, "error": "Cliente não encontrado"}), 404
    
    data = request.json
    
    try:
        if data.get('name'):
            client.name = data['name']
        if data.get('ad_account_id'):
            client.ad_account_id = data['ad_account_id']
        if data.get('pixel_id'):
            client.pixel_id = data['pixel_id']
        if data.get('access_token'):  # Only update if provided
            client.fb_access_token = data['access_token']
        if 'whatsapp_number' in data:
            client.whatsapp_number = data['whatsapp_number']
        
        db.session.commit()
        return jsonify({"success": True, "message": "Cliente atualizado!"})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/dashboard/clients/<int:client_id>', methods=['DELETE'])
@login_required
def delete_client(client_id):
    """Delete client and associated data"""
    if current_user.role == 'LOJISTA':
        return jsonify({"success": False, "error": "Sem permissão"}), 403
    
    client = ClientConfig.query.get(client_id)
    
    # Security check
    if not client or (client.gestor_id != current_user.id and current_user.role != 'MASTER'):
        return jsonify({"success": False, "error": "Cliente não encontrado"}), 404
    
    try:
        # Delete associated leads
        Lead.query.filter_by(client_id=client.user_id).delete()
        
        # Delete lojista user
        lojista = User.query.get(client.user_id)
        if lojista:
            db.session.delete(lojista)
        
        # Delete client config
        db.session.delete(client)
        db.session.commit()
        
        return jsonify({"success": True, "message": "Cliente deletado!"})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/dashboard/campaigns')
@login_required
def campaigns():
    conf = get_current_client_config()
    if not conf or not conf.fb_access_token or not conf.ad_account_id:
        flash("Configuração do Facebook incompleta para este cliente.", "error")
        return redirect(url_for('dashboard'))
        
    try:
        campaigns_data = get_active_campaigns(conf.fb_access_token, conf.ad_account_id)
    except Exception as e:
        flash(f"Erro ao buscar campanhas do Facebook: {str(e)}", "error")
        campaigns_data = []
    
    # Sidebar Context - support both MASTER and GESTOR
    if current_user.role == 'MASTER':
        clients = User.query.filter_by(role='LOJISTA').all()
    else:
        clients = User.query.filter_by(role='LOJISTA', parent_id=current_user.id).all()
    active_client = User.query.get(session.get('active_client_id'))
    
    return render_template('campaigns.html', campaigns=campaigns_data, clients=clients, active_client=active_client)

@app.route('/dashboard/campaign/<string:campaign_id>/adsets')
@login_required
def adsets(campaign_id):
    conf = get_current_client_config()
    if not conf: return redirect(url_for('dashboard'))
    
    url = f"https://graph.facebook.com/v19.0/{campaign_id}/adsets"
    params = {
        'access_token': conf.fb_access_token,
        'fields': 'name,status,adset_id,creative{name,image_url,thumbnail_url,body,title,object_story_spec}',
        'limit': 50
        # No filtering to include all ads for accurate spend
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        adsets_data = response.json().get('data', [])
    except:
        flash("Erro ao buscar conjuntos de anúncios.", "error")
        adsets_data = []
    
    # Sidebar Context - support both MASTER and GESTOR
    if current_user.role == 'MASTER':
        clients = User.query.filter_by(role='LOJISTA').all()
    else:
        clients = User.query.filter_by(role='LOJISTA', parent_id=current_user.id).all()
    active_client = User.query.get(session.get('active_client_id'))
    
    return render_template('adsets.html', adsets=adsets_data, clients=clients, active_client=active_client, campaign_id=campaign_id)

@app.route('/dashboard/adset/<string:adset_id>/ads')
@login_required
def ads(adset_id):
    conf = get_current_client_config()
    if not conf:
        return redirect(url_for('dashboard'))
    
    # Get date preset from query params (default to last_30d to match dashboard default)
    date_preset = request.args.get('date_preset', 'last_30d')
    
    # Use service to fetch ads for this specific adset with date filtering
    from facebook_service import get_client_ads_with_creatives
    ads_data = get_client_ads_with_creatives(
        conf.fb_access_token, 
        conf.ad_account_id, 
        adset_id=adset_id,
        date_preset=date_preset
    )


    
    # Sidebar Context - support both MASTER and GESTOR
    if current_user.role == 'MASTER':
        clients = User.query.filter_by(role='LOJISTA').all()
    else:
        clients = User.query.filter_by(role='LOJISTA', parent_id=current_user.id).all()
    active_client = User.query.get(session.get('active_client_id'))
    
    return render_template('ads.html', ads=ads_data, clients=clients, active_client=active_client, adset_id=adset_id)

# --- AI LAB ---

@app.route('/dashboard/ai-lab')
@login_required
def ai_lab():
    if current_user.role == 'LOJISTA': return redirect(url_for('client_app_home'))
    
    # Get Clients for Sidebar Selector
    clients = []
    if current_user.role == 'MASTER':
        clients = User.query.filter_by(role='LOJISTA').all()
    else:
        clients = User.query.filter_by(role='LOJISTA', parent_id=current_user.id).all()
    
    active_client_id = session.get('active_client_id')
    active_client = User.query.get(active_client_id) if active_client_id else None
    
    # If no client selected, select the first one
    if not active_client and clients:
        active_client = clients[0]
        session['active_client_id'] = active_client.id
    
    ads = []
    if active_client:
        conf = ClientConfig.query.filter_by(user_id=active_client.id).first()
        if conf and conf.fb_access_token and conf.ad_account_id:
            from facebook_service import get_client_ads_with_creatives
            # Fetch only recent active ads (last 30 days)
            ads = get_client_ads_with_creatives(
                conf.fb_access_token, 
                conf.ad_account_id,
                date_preset='last_30d'  # Only active recent ads
            )
            # Filter to only show ads with impressions > 0 (truly active)
            ads = [ad for ad in ads if ad.get('impressions', 0) > 0]
    
    
    return render_template('ai_lab.html', clients=clients, active_client=active_client, ads=ads)

@app.route('/api/ai-analyze', methods=['POST'])
@login_required
def ai_analyze():
    data = request.json
    ad_data = data.get('ad_data')
    objective = data.get('objective')
    
    if not ad_data:
        return jsonify({"success": False, "error": "Nenhum anúncio selecionado."})

    # Check if Gemini key is configured
    gemini_key = app.config.get('GEMINI_API_KEY')
    if not gemini_key or gemini_key == "cole_sua_chave_aqui":
        # Fallback to improved mock response
        return _generate_mock_analysis(ad_data, objective)
    
    # Real Google Gemini Analysis (FREE!)
    try:
        import google.generativeai as genai
        import requests as req
        from PIL import Image
        from io import BytesIO
        
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel('gemini-2.0-flash')  # Using the latest 2.0 Flash model
        
        # Download image
        img_response = req.get(ad_data.get('image_url'))
        img = Image.open(BytesIO(img_response.content))
        
        # Build prompt based on objective
        prompts = {
            'improve_copy': f"""Analise este anúncio do Facebook e sugira melhorias específicas:

TEXTO DO ANÚNCIO: {ad_data.get('body')}
NOME DO ANÚNCIO: {ad_data.get('name')}

Analise a IMAGEM anexa e forneça:

1. **Análise Visual** (o que você vê na imagem):
   - Produto/serviço identificado
   - Composição e cores
   - Qualidade da foto
   - Texto na imagem (se houver)
   - Destaque do produto

2. **Análise do Texto**:
   - Clareza da mensagem
   - Gatilhos mentais usados
   - Tom e persuasão

3. **Sugestões de Melhoria** (3 versões de copy mais persuasivas):
   - Versão com urgência
   - Versão com prova social
   - Versão focada em benefícios

4. **Melhorias para a Imagem**:
   - O que adicionar
   - O que remover
   - Sugestões de composição

Seja ESPECÍFICO e focado em AUMENTAR CONVERSÕES.""",

            'sentiment': f"""Analise o sentimento deste anúncio observando a IMAGEM anexa:

TEXTO: {ad_data.get('body')}

Identifique:
1. Tom geral (urgente, inspirador, informativo, relaxado, etc)
2. Emoções transmitidas pela IMAGEM (olhe cores, expressões, ambiente)
3. Emoções transmitidas pelo TEXTO
4. Alinhamento entre imagem e texto (estão em sintonia?)
5. Possíveis objeções ou preocupações do público-alvo

Seja detalhado sobre o que você VÊ na imagem.""",

            'headline': f"""Olhe a IMAGEM anexa e crie headlines impactantes:

TEXTO ATUAL: {ad_data.get('body')}

Baseado no que você VÊ na imagem, identifique o produto/serviço e gere 5 headlines que:
- Sejam curtas (máx 40 caracteres)
- Capturem atenção imediata  
- Estejam alinhadas com a imagem
- Usem gatilhos mentais (escassez, urgência, prova social, curiosidade)

Formato:
1. [emoji] Headline aqui
2. [emoji] Headline aqui
... etc""",

            'objections': f"""Analise a IMAGEM anexa e identifique objeções:

TEXTO: {ad_data.get('body')}

Baseado no que você VÊ na imagem, liste:

1. **Principais objeções** que o cliente pode ter:
   - Preço/valor
   - Qualidade
   - Confiança  
   - Entrega

2. **O que FALTA na imagem** para reduzir objeções:
   - Elementos visuais ausentes
   - Falta de prova social
   - Falta de garantias visuais

3. **O que FALTA no texto**:
   - Informações ausentes
   - Garantias não mencionadas

4. **Sugestões específicas** para quebrar cada objeção"""
        }
        
        # Generate content with image
        response = model.generate_content([
            prompts.get(objective, prompts['improve_copy']),
            img
        ])
        
        analysis_text = response.text
        return jsonify({"success": True, "result": analysis_text})
        
    except Exception as e:
        print(f"Gemini API Error: {e}")
        return _generate_mock_analysis(ad_data, objective)

def _generate_mock_analysis(ad_data, objective):
    """Improved mock analysis that actually uses the ad data"""
    body = ad_data.get('body', '')
    name = ad_data.get('name', '')
    
    # Extract keywords from body for more relevant response
    keywords = body.lower()
    
    if objective == 'improve_copy':
        analysis_text = (
            f"### 🧠 Análise de Copy & Criativo\n\n"
            f"**⚠️ Modo Demonstração** - Para análise completa com visão de imagem, configure a chave GRATUITA do Google Gemini.\n\n"
            f"**Texto Original:**\n{body}\n\n"
            f"**Sugestões de Copy Melhorada:**\n\n"
            f"**Versão 1 (Urgência):**\n"
            f"🔥 {body[:50]}... Últimas unidades! Garanta a sua agora.\n\n"
            f"**Versão 2 (Prova Social):**\n"
            f"⭐ +1000 clientes satisfeitos! {body[:40]}... Junte-se a eles!\n\n"
            f"**Versão 3 (Benefício):**\n"
            f"✨ Transforme seu estilo. Clique e descubra!\n\n"
            f"**Como ativar análise REAL:** Pegue sua chave grátis em https://aistudio.google.com/app/apikey"
        )
    elif objective == 'sentiment':
        analysis_text = (
            f"### 🌡️ Análise de Sentimento\n\n"
            f"**Tom Detectado:** Baseado no texto '{body[:30]}...', o tom parece ser "
            f"{'inspirador e motivacional' if any(w in keywords for w in ['inspirada', 'força', 'essência']) else 'comercial e direto'}.\n\n"
            f"**Emoções Principais:**\n"
            f"- Aspiração e identidade\n"
            f"- Conexão com valores\n\n"
            f"**⚠️ Para análise visual completa da IMAGEM, configure a chave do Google Gemini (gratuita).**"
        )
    elif objective == 'headline':
        product_hint = name if len(name) < 30 else body[:20]
        analysis_text = (
            f"### ✍️ Sugestões de Headlines\n\n"
            f"1. 🛑 Pare tudo! Você precisa ver isto\n"
            f"2. 💎 {product_hint} - Exclusivo e Limitado\n"
            f"3. ✨ O segredo que todos querem saber\n"
            f"4. 🔥 Oferta imperdível - Últimas unidades\n"
            f"5. 🎯 Feito especialmente para VOCÊ\n\n"
            f"**💡 Dica:** Com a API do Google Gemini (grátis), as headlines serão personalizadas baseadas na IMAGEM real do anúncio!"
        )
    else:  # objections
        analysis_text = (
            f"### 🛡️ Análise de Objeções\n\n"
            f"**Possíveis objeções do cliente:**\n"
            f"- 'Será que é de qualidade?' → Adicione prova social ou selo na imagem\n"
            f"- 'Preço vale a pena?' → Destaque o valor/benefício no texto\n"
            f"- 'Vai chegar rápido?' → Mencione prazo de entrega ou frete grátis\n"
            f"- 'Posso confiar?' → Mostre avaliações ou garantia\n\n"
            f"**⚠️ Para análise visual das objeções, configure o Google Gemini (100% gratuito).**"
        )

    import time
    time.sleep(1.0)
    return jsonify({"success": True, "result": analysis_text})

@app.route('/api/ai-chat', methods=['POST'])
@login_required
def ai_chat():
    """Chat endpoint for conversational AI about selected ad"""
    data = request.json
    message = data.get('message', '')
    ad_context = data.get('ad_context', {})
    history = data.get('history', [])
    
    gemini_key = app.config.get('GEMINI_API_KEY')
    
    if not gemini_key or gemini_key == "cole_sua_chave_aqui":
        return jsonify({
            "success": False, 
            "error": "Configure sua chave do Gemini para usar o chat."
        })
    
    try:
        import google.generativeai as genai
        import requests as req
        from PIL import Image
        from io import BytesIO
        
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Download image
        img_response = req.get(ad_context.get('image_url'))
        img = Image.open(BytesIO(img_response.content))
        
        # Build context prompt
        context_prompt = f"""Você é um especialista em marketing digital e análise de criativos.

CONTEXTO DO ANÚNCIO:
- Texto Principal: {ad_context.get('body', 'Não informado')}
- Título: {ad_context.get('title', 'Não informado')}
- Nome: {ad_context.get('name', 'Não informado')}

Analise a IMAGEM anexa e responda às perguntas do usuário de forma objetiva e prática. Seja específico sobre o que você vê na imagem."""
        
        # Build conversation history
        conversation = []
        if history:
            for msg in history[-5:]:  # Keep last 5 messages for context
                role = "user" if msg.get('role') == 'user' else "model"
                conversation.append({'role': role, 'parts': [msg.get('content', '')]})
        
        # Start chat with context
        chat = model.start_chat(history=conversation)
        
        # Send message with image on first interaction
        if not history:
            response = chat.send_message([context_prompt, message, img])
        else:
            response = chat.send_message(message)
        
        return jsonify({
            "success": True, 
            "message": response.text
        })
        
    except Exception as e:
        print(f"Chat Error: {e}")
        return jsonify({
            "success": False,
            "error": f"Erro ao processar mensagem: {str(e)}"
        })

# --- USER MANAGEMENT ---

@app.route('/admin/users', methods=['GET', 'POST'])
@login_required
def users_list():
    if current_user.role == 'LOJISTA':
        return redirect(url_for('client_app_home'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        
        # Create User
        new_user = User(username=username, 
                        password_hash=generate_password_hash(password, method='pbkdf2:sha256'),
                        role=role,
                        parent_id=current_user.id)
        db.session.add(new_user)
        db.session.commit()
        
        # If Lojista, create Config
        if role == 'LOJISTA':
            conf = ClientConfig(user_id=new_user.id)
            db.session.add(conf)
            db.session.commit()
            
        flash(f"Usuário {username} criado com sucesso!", "success")
        return redirect(url_for('users_list'))
    
    # List Users with stats
    users = []
    if current_user.role == 'MASTER':
        all_users = User.query.filter(User.id != current_user.id).all()
    else:
        all_users = User.query.filter_by(parent_id=current_user.id).all()
    
    # Add stats for each user
    for user in all_users:
        user_data = {
            'id': user.id,
            'username': user.username,
            'role': user.role,
            'created_at': user.id,  # Using ID as proxy for creation order
            'leads_count': 0,
            'sales_count': 0,
            'has_config': False
        }
        
        if user.role == 'LOJISTA':
            user_data['leads_count'] = Lead.query.filter_by(client_id=user.id).count()
            user_data['sales_count'] = Lead.query.filter_by(client_id=user.id, status='SOLD').count()
            conf = ClientConfig.query.filter_by(user_id=user.id).first()
            user_data['has_config'] = bool(conf and conf.fb_access_token)
        
        users.append(user_data)
        
    return render_template('users.html', users=users)

@app.route('/admin/users/<int:user_id>/edit', methods=['POST'])
@login_required
def edit_user(user_id):
    if current_user.role != 'MASTER':
        return jsonify({"success": False, "error": "Sem permissão"}), 403
    
    user = User.query.get(user_id)
    if not user or user.role == 'MASTER':
        return jsonify({"success": False, "error": "Usuário não encontrado"}), 404
    
    data = request.json
    
    if 'username' in data and data['username']:
        # Check if username already exists
        existing = User.query.filter(User.username == data['username'], User.id != user_id).first()
        if existing:
            return jsonify({"success": False, "error": "Usuário já existe"}), 400
        user.username = data['username']
    
    if 'password' in data and data['password']:
        user.password_hash = generate_password_hash(data['password'], method='pbkdf2:sha256')
    
    db.session.commit()
    return jsonify({"success": True, "message": "Usuário atualizado!"})

@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    if current_user.role != 'MASTER':
        return jsonify({"success": False, "error": "Sem permissão"}), 403
    
    user = User.query.get(user_id)
    if not user or user.role == 'MASTER':
        return jsonify({"success": False, "error": "Não pode deletar este usuário"}), 404
    
    # Delete related data
    if user.role == 'LOJISTA':
        Lead.query.filter_by(client_id=user.id).delete()
        ClientConfig.query.filter_by(user_id=user.id).delete()
    
    db.session.delete(user)
    db.session.commit()
    
    return jsonify({"success": True, "message": "Usuário deletado!"})

# --- CLIENT APP ---

@app.route('/app')
@login_required
def client_app_home():
    if current_user.role != 'LOJISTA':
        return redirect(url_for('dashboard'))
        
    leads = Lead.query.filter_by(client_id=current_user.id, status='CLICKED').order_by(Lead.timestamp.desc()).all()
    return render_template('client.html', leads=leads)

@app.route('/api/update_status', methods=['POST'])
@login_required
def update_status():
    data = request.json
    short_id = data.get('short_id')
    status = data.get('status')
    value = data.get('value')
    
    lead = Lead.query.get(short_id)
    if not lead or lead.client_id != current_user.id:
        return jsonify({"success": False, "error": "Unauthorized"}), 403
        
    lead.status = status
    if value:
        lead.sale_value = value
    db.session.commit()
    
    # CAPI
    conf = get_current_client_config()
    if conf and conf.fb_access_token and conf.pixel_id:
        user_data = {'ip_address': lead.ip_address, 'user_agent': lead.user_agent}
        if status == 'HOT':
            send_event("AddToCart", lead.fbclid, user_data, {"value": 0, "currency": "BRL"}, conf.fb_access_token, conf.pixel_id)
        elif status == 'SOLD':
            send_event("Purchase", lead.fbclid, user_data, {"value": value, "currency": "BRL"}, conf.fb_access_token, conf.pixel_id)
            
    return jsonify({"success": True})

# --- MIDDLEWARE ---

@app.route('/middleware')
def middleware():
    phone = request.args.get('phone')
    text = request.args.get('text', '')
    fbclid = request.args.get('fbclid')
    # For multi-tenant, we need to know WHICH client this is for.
    # In a real app, the link would contain a client_id or hash.
    # For MVP, let's assume we pass client_id in URL or just use the first one found?
    # Better: Add client_id param to the link generator.
    client_id = request.args.get('client_id')
    
    if not client_id:
        return "Missing client_id", 400

    ip = request.remote_addr
    ua = request.headers.get('User-Agent')
    
    new_lead = Lead(fbclid=fbclid, ip_address=ip, user_agent=ua, client_id=client_id)
    db.session.add(new_lead)
    db.session.commit()
    
    final_text = f"{text} (#{new_lead.short_id})"
    encoded_text = urllib.parse.quote(final_text)
    wa_url = f"https://wa.me/{phone}?text={encoded_text}"
    
    return redirect(wa_url)

# --- INIT DB ---
with app.app_context():
    db.create_all()
    # Create Master User if not exists
    if not User.query.filter_by(username='master').first():
        master = User(username='master', password_hash=generate_password_hash('admin123', method='pbkdf2:sha256'), role='MASTER')
        db.session.add(master)
        db.session.commit()

if __name__ == '__main__':
    app.run(debug=True, port=8000)
