import streamlit as st
import pandas as pd
import os
import time
from facebook_business.ad_objects.server_side.event import Event
from facebook_business.ad_objects.server_side.event_request import EventRequest
from facebook_business.ad_objects.server_side.user_data import UserData
from facebook_business.ad_objects.server_side.custom_data import CustomData
from facebook_business.api import FacebookAdsApi

# --- CONFIGURATION ---
PIXEL_ID = "864336215799285"
ACCESS_TOKEN = "EAAQqASJtmX0BQCo4ZAZBt81b2Qu0OamefUjx2EYO7DT4e6OZCwhm7OqbPuGdETqc5Jictp35Hk11NJMtOXRQ3jwU7ZAwYZB22S0QHQ6nlHee1kdpIBgZB7eURwdQX2hPtW9kKR2Wa1j0TTZCyuPp5chZAQimSpkfPUhqOrg8ZCLRHLRLqwSci5PrW6WOm9pPMCPBtEgZDZD"
LINKS_FILE = "links.csv"

# Initialize Facebook API
try:
    FacebookAdsApi.init(access_token=ACCESS_TOKEN)
except Exception as e:
    st.error(f"Erro ao inicializar API do Facebook: {e}")

def save_link(phone, campaign):
    """Salva o link gerado no arquivo CSV."""
    if not os.path.exists(LINKS_FILE):
        df = pd.DataFrame(columns=["id", "phone", "campaign", "created_at"])
    else:
        df = pd.read_csv(LINKS_FILE)
    
    new_id = len(df)
    new_row = pd.DataFrame({
        "id": [new_id],
        "phone": [phone],
        "campaign": [campaign],
        "created_at": [pd.Timestamp.now()]
    })
    
    df = pd.concat([df, new_row], ignore_index=True)
    df.to_csv(LINKS_FILE, index=False)
    return new_id

def get_link_data(link_id):
    """Recupera os dados do link pelo ID."""
    if not os.path.exists(LINKS_FILE):
        return None
    
    df = pd.read_csv(LINKS_FILE)
    row = df[df["id"] == int(link_id)]
    
    if row.empty:
        return None
    return row.iloc[0]

def send_capi_event(user_data_params, event_source_url):
    """Envia evento de Lead para o Facebook CAPI."""
    try:
        user_data = UserData(
            client_ip_address=user_data_params.get('client_ip_address'),
            client_user_agent=user_data_params.get('client_user_agent'),
            fbc=user_data_params.get('fbc'),
            fbp=user_data_params.get('fbp')
        )

        event = Event(
            event_name="Lead",
            event_time=int(time.time()),
            user_data=user_data,
            event_source_url=event_source_url,
            action_source="website"
        )

        events = [event]

        event_request = EventRequest(
            events=events,
            pixel_id=PIXEL_ID
        )

        event_response = event_request.execute()
        return True, event_response
    except Exception as e:
        return False, str(e)

# --- APP LOGIC ---

# Check for ID in URL parameters
query_params = st.query_params
link_id = query_params.get("id")

if link_id:
    # --- BACKEND LOGIC (REDIRECT) ---
    st.title("Redirecionando...")
    
    data = get_link_data(link_id)
    
    if data is not None:
        phone = data["phone"]
        
        # Capture User Data
        # Note: Streamlit runs on the server, so getting client IP/User Agent directly 
        # is tricky without a reverse proxy or specific headers. 
        # We will try to get from headers if available, or use placeholders/simulated data as requested.
        
        # In a real deployment behind a proxy (like Streamlit Cloud), headers might be available.
        # For local dev, these might be None.
        # Streamlit doesn't expose raw request headers easily in the script context without hacks.
        # We will use best effort or placeholders as per "simulado ou real".
        
        client_ip = "127.0.0.1" # Placeholder/Localhost
        user_agent = "Mozilla/5.0 (Compatible; ZapTrack/1.0)" # Placeholder
        
        # Try to get fbclid from URL
        fbclid = query_params.get("fbclid")
        fbc = f"fb.1.{int(time.time())}.{fbclid}" if fbclid else None
        
        user_data_params = {
            "client_ip_address": client_ip,
            "client_user_agent": user_agent,
            "fbc": fbc
        }
        
        # Send Event
        success, response = send_capi_event(user_data_params, event_source_url=f"https://zaptrack.streamlit.app/?id={link_id}")
        
        if success:
            print("Evento enviado com sucesso!")
        else:
            print(f"Falha ao enviar evento: {response}")
            # Não paramos o redirecionamento por falha no evento
            
        # Redirect
        whatsapp_url = f"https://wa.me/{phone}"
        
        # Meta refresh for redirection
        st.markdown(f'<meta http-equiv="refresh" content="2;url={whatsapp_url}">', unsafe_allow_html=True)
        st.write(f"Você está sendo redirecionado para o WhatsApp...")
        st.write("Se não for redirecionado automaticamente, clique no link abaixo:")
        st.markdown(f"[Clique aqui para ir para o WhatsApp]({whatsapp_url})")
        
    else:
        st.error("Link inválido ou não encontrado.")

else:
    # --- FRONTEND LOGIC (CREATE) ---
    st.title("ZapTrack MVP 🚀")
    st.subheader("Gerador de Links de Rastreamento WhatsApp + CAPI")

    with st.form("create_link_form"):
        phone_input = st.text_input("Número do WhatsApp (apenas números)", placeholder="555199999999")
        campaign_input = st.text_input("Nome da Campanha", placeholder="black_friday")
        
        submitted = st.form_submit_button("Gerar Link de Rastreamento")
        
        if submitted:
            if phone_input and campaign_input:
                if not phone_input.isdigit():
                    st.error("O número do WhatsApp deve conter apenas dígitos.")
                else:
                    new_id = save_link(phone_input, campaign_input)
                    
                    # Base URL detection (best effort)
                    # In local dev it's usually localhost:8501
                    base_url = "http://localhost:8501" 
                    generated_link = f"{base_url}/?id={new_id}"
                    
                    st.success("Link gerado com sucesso!")
                    st.code(generated_link, language="text")
                    st.info("⚠️ IMPORTANTE: Substitua 'http://localhost:8501' pela URL final do seu aplicativo quando fizer o deploy.")
                    
                    # Show preview of data
                    if os.path.exists(LINKS_FILE):
                        st.write("Últimos links gerados:")
                        st.dataframe(pd.read_csv(LINKS_FILE).tail(5))
            else:
                st.warning("Por favor, preencha todos os campos.")
