#!/usr/bin/env python3
"""
Add client Caetana to existing database
"""
import os
from app import app, db
from models import User, ClientConfig
from werkzeug.security import generate_password_hash

with app.app_context():
    # Check if caetana already exists
    existing = User.query.filter_by(username='caetana').first()
    if existing:
        print("⚠️  Cliente 'caetana' já existe!")
        print(f"   ID: {existing.id}, Role: {existing.role}")
    else:
        # Get gestor (admin's child or first gestor)
        gestor = User.query.filter_by(role='GESTOR').first()
        if not gestor:
            print("❌ ERRO: Nenhum gestor encontrado. Crie um gestor primeiro.")
            exit(1)
        
        # Create caetana user
        caetana = User(
            username='caetana',
            password_hash=generate_password_hash('caetana123', method='pbkdf2:sha256'),
            role='LOJISTA',
            parent_id=gestor.id
        )
        db.session.add(caetana)
        db.session.commit()
        print(f"✅ Cliente 'caetana' criado! (ID: {caetana.id})")
        
        # Get Facebook credentials from secrets or use placeholders
        try:
            import toml
            secrets = toml.load('.streamlit/secrets.toml')
            fb_token = secrets.get('FB_ACCESS_TOKEN', 'PLACEHOLDER_TOKEN')
            ad_account = secrets.get('AD_ACCOUNT_ID', 'PLACEHOLDER_ACCOUNT')
            pixel_id = secrets.get('PIXEL_ID', '123456789')
        except:
            fb_token = 'PLACEHOLDER_TOKEN'
            ad_account = 'PLACEHOLDER_ACCOUNT'
            pixel_id = '123456789'
        
        # Create Facebook config
        config = ClientConfig(
            user_id=caetana.id,
            gestor_id=gestor.id,
            name='Caetana',
            fb_access_token=fb_token,
            ad_account_id=ad_account,
            pixel_id=pixel_id
        )
        db.session.add(config)
        db.session.commit()
        print("✅ Configuração Facebook criada para 'caetana'")
    
    # Show all clients
    print("\n" + "="*50)
    print("CLIENTES CADASTRADOS:")
    print("="*50)
    clients = User.query.filter_by(role='LOJISTA').all()
    for c in clients:
        config = ClientConfig.query.filter_by(user_id=c.id).first()
        print(f"\n{c.username}:")
        print(f"  Password: {c.username}123")
        print(f"  ID: {c.id}")
        if config:
            print(f"  Config: ✅ ({config.name})")
            print(f"  Ad Account: {config.ad_account_id}")
        else:
            print(f"  Config: ❌ NÃO CONFIGURADO")
