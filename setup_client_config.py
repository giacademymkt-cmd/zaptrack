"""
Script to setup ClientConfig for lojista1 using credentials from secrets.toml
"""
from app import app, db
from models import User, ClientConfig
import toml

# Load secrets
secrets = toml.load('.streamlit/secrets.toml')

with app.app_context():
    # Find lojista1
    lojista = User.query.filter_by(username='lojista1').first()
    
    if not lojista:
        print("❌ User 'lojista1' not found. Please create it first.")
    else:
        # Check if config already exists
        existing_config = ClientConfig.query.filter_by(user_id=lojista.id).first()
        
        if existing_config:
            # Update
            existing_config.fb_access_token = secrets['FB_ACCESS_TOKEN']
            existing_config.ad_account_id = secrets['AD_ACCOUNT_ID']
            existing_config.pixel_id = secrets['PIXEL_ID']
            print(f"✅ Updated ClientConfig for {lojista.username}")
        else:
            # Create new
            config = ClientConfig(
                user_id=lojista.id,
                fb_access_token=secrets['FB_ACCESS_TOKEN'],
                ad_account_id=secrets['AD_ACCOUNT_ID'],
                pixel_id=secrets['PIXEL_ID']
            )
            db.session.add(config)
            print(f"✅ Created ClientConfig for {lojista.username}")
        
        db.session.commit()
        print(f"✅ Configuração salva com sucesso!")
        print(f"   - Ad Account ID: {secrets['AD_ACCOUNT_ID']}")
        print(f"   - Pixel ID: {secrets['PIXEL_ID']}")
