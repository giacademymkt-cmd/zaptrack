import streamlit as st
from database import get_active_leads, update_lead_status, get_lead
from facebook_capi import send_event
import time

def render_client_view():
    st.title("ZAP TRACK ⚡")
    st.caption("Painel do Lojista")

    # Fetch active leads
    leads = get_active_leads()

    if leads.empty:
        st.info("Nenhum lead pendente no momento. 🎉")
        return

    for index, row in leads.iterrows():
        short_id = row['short_id']
        timestamp = row['timestamp']
        
        # Calculate time ago
        try:
            ts = pd.to_datetime(timestamp)
            time_diff = pd.Timestamp.now() - ts
            minutes_ago = int(time_diff.total_seconds() / 60)
            time_str = f"Há {minutes_ago} min"
        except:
            time_str = str(timestamp)

        # Lead Card
        with st.container():
            st.markdown(f"""
                <div class="lead-card">
                    <h3>Lead #{short_id}</h3>
                    <p>{time_str}</p>
                </div>
            """, unsafe_allow_html=True)
            
            # Action Buttons (Funnel)
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # Hot Lead (AddToCart)
                if st.button("🔥 Quente", key=f"btn_hot_{short_id}"):
                    # Update DB
                    update_lead_status(short_id, 'HOT')
                    
                    # Send CAPI
                    if "FB_ACCESS_TOKEN" in st.secrets and "PIXEL_ID" in st.secrets:
                        lead_data = get_lead(short_id)
                        user_data = {
                            'ip_address': lead_data['ip_address'],
                            'user_agent': lead_data['user_agent']
                        }
                        # AddToCart usually doesn't have a value, or we can estimate
                        success, resp = send_event(
                            "AddToCart",
                            lead_data['fbclid'],
                            user_data,
                            {"currency": "BRL", "value": 0}, # Optional value
                            st.secrets["FB_ACCESS_TOKEN"],
                            st.secrets["PIXEL_ID"]
                        )
                        if success:
                            st.toast(f"Lead #{short_id} marcado como QUENTE! 🔥")
                        else:
                            st.error(f"Erro CAPI: {resp}")
                    
                    time.sleep(1)
                    st.rerun()

            with col2:
                # Sale (Purchase)
                if st.button("✅ Venda", key=f"btn_sell_{short_id}", type="primary"):
                    st.session_state[f'selling_{short_id}'] = True
            
            with col3:
                # Archive (Dismiss)
                if st.button("❌ Arquivar", key=f"btn_archive_{short_id}"):
                    update_lead_status(short_id, 'ARCHIVED')
                    st.rerun()

            # Sale Input Logic
            if st.session_state.get(f'selling_{short_id}', False):
                with st.form(key=f"form_{short_id}"):
                    st.markdown("### Confirmar Venda")
                    value = st.number_input("Valor (R$)", min_value=0.0, step=10.0, format="%.2f")
                    submit = st.form_submit_button("💰 CONFIRMAR", type="primary")
                    
                    if submit:
                        # 1. Update DB
                        update_lead_status(short_id, 'SOLD', value)
                        
                        # 2. Send CAPI
                        if "FB_ACCESS_TOKEN" in st.secrets and "PIXEL_ID" in st.secrets:
                            lead_data = get_lead(short_id)
                            user_data = {
                                'ip_address': lead_data['ip_address'],
                                'user_agent': lead_data['user_agent']
                            }
                            success, resp = send_event(
                                "Purchase",
                                lead_data['fbclid'],
                                user_data,
                                {"currency": "BRL", "value": value},
                                st.secrets["FB_ACCESS_TOKEN"],
                                st.secrets["PIXEL_ID"]
                            )
                            if success:
                                st.success("Venda registrada! 🚀")
                            else:
                                st.error(f"Erro CAPI: {resp}")
                        else:
                            st.warning("Venda salva, mas Pixel não configurado.")
                        
                        time.sleep(2)
                        st.rerun()
