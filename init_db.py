#!/usr/bin/env python3
"""
Script de inicialização do banco de dados para production (Render)
"""
import os
from app import app, db

with app.app_context():
    # Criar todas as tabelas
    db.create_all()
    print("✅ Database initialized successfully!")
    
    # Verificar se já existe um usuário MASTER
    from models import User
    from werkzeug.security import generate_password_hash
    
    master = User.query.filter_by(role='MASTER').first()
    if not master:
        # Criar usuário MASTER padrão
        master_user = User(
            username='admin',
            password_hash=generate_password_hash('admin123', method='pbkdf2:sha256'),
            role='MASTER'
        )
        db.session.add(master_user)
        db.session.commit()
        print("✅ Master user created! Username: admin, Password: admin123")
        print("⚠️  CHANGE THE PASSWORD IMMEDIATELY AFTER FIRST LOGIN!")
    else:
        print("ℹ️  Master user already exists")
