from app import app

# Dette er nu det korrekte entry point for wfastcgi
if __name__ == '__main__':
    import os
    # Hent port fra miljøvariabel (Azure App Service sætter PORT)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
