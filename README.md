# AgencyOS - Marketing Agency Management Platform

🚀 **Sistema completo de gestão de agência de marketing com integração ao Facebook Ads API**

## 🎯 Funcionalidades

- **Dashboard Premium** com métricas em tempo real
- **Integração Facebook Ads API** para campanhas, conjuntos e anúncios
- **Análise Demográfica** (idade, gênero, plataforma, localização)
- **Conversions API (CAPI)** para rastreamento de vendas
- **Multi-tenant** com roles (MASTER, GESTOR, LOJISTA)
- **AI Lab** com Google Gemini para análise de criativos

## 🛠️ Tech Stack

- **Backend:** Flask 3.0, SQLAlchemy
- **Frontend:** Tailwind CSS, Chart.js
- **Database:** SQLite (dev) / PostgreSQL (prod)
- **AI:** Google Gemini API
- **APIs:** Facebook Graph API, Facebook CAPI

## 🚀 Deploy Rápido (Render)

1. Fork este repositório
2. Conecte no [Render.com](https://render.com)
3. Configure a variável `GEMINI_API_KEY`
4. Deploy automático! ✨

📖 **[Guia completo de deployment](docs/render_deployment_guide.md)**

## 🔑 Primeiro Acesso

Após o deploy:
- **URL:** `https://seu-app.onrender.com`
- **Login:** `admin`
- **Senha:** `admin123` (mude imediatamente!)

## 💻 Desenvolvimento Local

```bash
# Clonar
git clone https://github.com/seu-usuario/facebook_ads_dashboard.git
cd facebook_ads_dashboard

# Instalar dependências
pip install -r requirements.txt

# Configurar secrets
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edite .streamlit/secrets.toml com suas chaves

# Inicializar DB
python init_db.py

# Rodar
python app.py
```

Acesse: `http://localhost:8000`

## 📁 Estrutura

```
facebook_ads_dashboard/
├── app.py                  # Aplicação principal Flask
├── models.py               # Modelos SQLAlchemy
├── facebook_service.py     # Integração Facebook Ads API
├── facebook_capi.py        # Conversions API
├── init_db.py              # Inicialização do banco
├── templates/              # Templates Jinja2
├── static/                 # CSS, JS, imagens
├── render.yaml             # Config Render
└── requirements.txt        # Dependências Python
```

## 🔐 Variáveis de Ambiente

| Variável | Descrição |
|----------|-----------|
| `SECRET_KEY` | Chave secreta do Flask |
| `GEMINI_API_KEY` | Google Gemini API Key |
| `DATABASE_URL` | URL do banco (auto no Render) |

## 📝 Licença

MIT License - veja [LICENSE](LICENSE) para detalhes.

## 🤝 Contribuindo

Pull requests são bem-vindos! Para mudanças maiores, abra uma issue primeiro.

---

**Desenvolvido com ❤️ usando Flask e Google Gemini**
