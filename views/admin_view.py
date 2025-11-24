import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from database import get_all_leads
import urllib.parse
from facebook_service import get_active_campaigns, get_campaign_insights

def render_admin_view():
    st.title("ZAP TRACK - Admin 🛠️")
    
    # 1. Configuration Check
    if "FB_ACCESS_TOKEN" not in st.secrets or "PIXEL_ID" not in st.secrets:
        st.error("⚠️ Configuração incompleta! Adicione `FB_ACCESS_TOKEN` e `PIXEL_ID` ao `.streamlit/secrets.toml`.")
    else:
        st.success(f"✅ Pixel Ativo: {st.secrets['PIXEL_ID']}")

    # --- ANALYTICS DASHBOARD ---
    st.header("Analytics 📊")
    
    df = get_all_leads()
    
    if not df.empty:
        # Calculate Metrics
        total_leads = len(df)
        total_sales = len(df[df['status'] == 'SOLD'])
        total_revenue = df['sale_value'].sum()
        conversion_rate = (total_sales / total_leads * 100) if total_leads > 0 else 0
        
        # Fetch Ad Spend (Real Data)
        ad_spend = 0.0
        if "FB_ACCESS_TOKEN" in st.secrets and "AD_ACCOUNT_ID" in st.secrets:
            try:
                # Fetch spend for last 30 days or max
                # Simplified: Get insights for account level would be better, but iterating campaigns works for MVP
                campaigns = get_active_campaigns(st.secrets["FB_ACCESS_TOKEN"], st.secrets["AD_ACCOUNT_ID"])
                for camp in campaigns:
                    insights = get_campaign_insights(st.secrets["FB_ACCESS_TOKEN"], camp['id'])
                    if insights:
                        ad_spend += float(insights[0].get('spend', 0))
            except Exception as e:
                st.warning(f"Erro ao buscar gastos do Facebook: {e}")

        roas = (total_revenue / ad_spend) if ad_spend > 0 else 0

        # Top KPIs
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Leads (Cliques)", total_leads)
        col2.metric("Vendas Confirmadas", total_sales)
        col3.metric("Receita (R$)", f"{total_revenue:,.2f}")
        col4.metric("ROAS Real", f"{roas:.2f}x", delta_color="normal")

        # Charts
        c1, c2 = st.columns([1, 2])
        
        with c1:
            # Donut Chart: Conversion Rate
            labels = ['Vendas', 'Outros']
            values = [total_sales, total_leads - total_sales]
            colors = ['#25D366', '#262730'] # WhatsApp Green, Dark Card
            
            fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=.7, marker_colors=colors)])
            fig.update_layout(
                title_text="Taxa de Conversão",
                showlegend=False,
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#FAFAFA'),
                margin=dict(t=40, b=0, l=0, r=0),
                height=250
            )
            st.plotly_chart(fig, use_container_width=True)

        with c2:
            # Recent Leads Table (Styled)
            st.subheader("Últimos Leads")
            display_df = df[['short_id', 'timestamp', 'status', 'sale_value']].copy()
            st.dataframe(display_df, use_container_width=True, height=250)

    else:
        st.info("Nenhum dado para exibir ainda.")

    # --- LINK GENERATOR ---
    st.markdown("---")
    st.header("Gerador de Links 🔗")
    with st.form("link_gen"):
        phone = st.text_input("WhatsApp do Lojista (com DDI e DDD, apenas números)", value="55")
        message = st.text_input("Mensagem Padrão", value="Olá, vi o anúncio da promoção!")
        submitted = st.form_submit_button("Gerar Link de Rastreamento")
        
        if submitted and phone:
            base_url = "http://localhost:8501" 
            encoded_msg = urllib.parse.quote(message)
            tracking_link = f"{base_url}/?phone={phone}&text={encoded_msg}"
            st.code(tracking_link, language="text")
            st.caption("Use este link nos seus anúncios do Facebook Ads.")
