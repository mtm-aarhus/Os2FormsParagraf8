import os
import sys
import logging
import json
import traceback
import requests
from flask import Flask, request, jsonify
from sqlalchemy import text
from database_handler import DatabaseHandler

# Konfigurer logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("os2forms_webhook")

def hent_os2_submission(submission_url: str) -> dict:
    """Henter submission data fra OS2Forms med API-nøgle."""
    api_key = os.environ.get("OS2FORMS_API_KEY")
    if not api_key:
        raise EnvironmentError("API-nøglen OS2FORMS_API_KEY er ikke sat i miljøet.")

    headers = {
        "api-key": api_key
    }

    response = requests.get(submission_url, headers=headers)
    response.raise_for_status()
    return response.json()

# Log miljøinformation
logger.info(f"Python version: {sys.version}")
logger.info(f"Kører i Azure: {'WEBSITE_SITE_NAME' in os.environ}")
if 'WEBSITE_SITE_NAME' in os.environ:
    logger.info(f"App Service navn: {os.environ.get('WEBSITE_SITE_NAME')}")

# Log API-nøgle status
if os.environ.get("OS2FORMS_API_KEY"):
    logger.info("OS2FORMS_API_KEY er sat i miljøvariablerne")
else:
    logger.warning("OS2FORMS_API_KEY er IKKE sat i miljøvariablerne - webhook vil ikke virke korrekt")

# Flask app
app = Flask(__name__)

# Global database handler
db_handler = DatabaseHandler(initialize_db=True)

@app.route("/")
def index():
    logger.info("Hjemmeside tilgået")
    return "OS2Forms Webhook Endpoint er aktiv", 200

@app.route("/healthcheck", methods=["GET"])
def healthcheck():
    try:
        with db_handler.get_connection() as conn:
            result = conn.execute(text("SELECT 1"))
            result = result.fetchone()
            return jsonify({"status": "ok", "sql_result": result[0]}), 200
    except Exception as e:
        import traceback
        return jsonify({
            "status": "error",
            "message": str(e),
            "trace": traceback.format_exc()
        }), 500

@app.route('/os2forms/webhook', methods=['POST'])
def os2forms_webhook():
    try:
        # Log webhook modtagelse
        logger.info("Webhook modtaget")
        
        # Hent JSON data fra request
        request_data = request.get_json()
        logger.info(f"Modtaget data med nøgler: {list(request_data.keys())}")
        logger.info(f"Raw request data: {json.dumps(request_data, indent=2)[:500]}...")
        
        # Gem rå webhook data
        try:
            db_handler = DatabaseHandler(initialize_db=True)
            db_handler.gem_webhook_data(json.dumps(request_data))
            logger.info("Raw webhook data gemt i webhook_data tabel")
        except Exception as e:
            logger.error(f"Fejl ved gemning af raw webhook data: {str(e)}")
            # Fortsæt alligevel - vi vil gerne prøve at hente submission data
        
        # Hent submission URL
        links = request_data.get('links', {})
        submission_url = links.get('get_submission_url')
        if not submission_url:
            logger.error("Ingen submission URL fundet i request")
            raise ValueError("Ingen submission URL fundet i request")
            
        logger.info(f"Henter submission data fra: {submission_url}")
        
        # Hent submission data fra URL med API-nøgle
        try:
            submission_data = hent_os2_submission(submission_url)
            logger.info(f"Submission data hentet fra URL (slutter med: {submission_url[-10:]})")            
        except Exception as e:
            logger.error(f"Kunne ikke hente submission data: {str(e)}")
            raise ValueError(f"Kunne ikke hente submission data: {str(e)}")
        
        # Udpak data fra submission_data
        data = submission_data.get('data', {})
        entity = submission_data.get('entity', {})
        
        # Forbered submission data
        submission_dict = {
            'udfylder': data.get('udfylder', 'Ukendt'),
            'vaelg_dato_for_ansoegning': data.get('vaelg_dato_for_ansoegning', '2025-01-01'),
            'bemaerkninger': data.get('bemaerkninger', ''),
            'udfylder_rolle': data.get('er_udfylder_grundejer_raadgiver_bygherre_eller_andet', 'Ukendt'),
            'submission_id': entity.get('sid', [{}])[0].get('value', ''),
            'created_at': entity.get('created', [{}])[0].get('value', ''),
            'completed_at': entity.get('completed', [{}])[0].get('value', '')
        }
        
        # Udpak og forbered adresser
        addresses = data.get('adresser', [])
        logger.info(f"Fundet {len(addresses)} adresser")
        
        # Udpak og forbered kontaktoplysninger
        contact_info = []
        udfylder_rolle = data.get('er_udfylder_grundejer_raadgiver_bygherre_eller_andet')
        
        # Tilføj udfylders kontaktoplysninger baseret på rolle
        if udfylder_rolle in ['Rådgiver', 'Bygherre', 'Grundejer']:
            if udfylder_rolle == 'Bygherre':
                udfylder_info = data.get('kontaktoplysninger_for_bygherre', {})
            elif udfylder_rolle == 'Rådgiver':
                udfylder_info = data.get('kontaktoplysninger_for_raadgiver', {})
            else:  # Grundejer
                udfylder_info = data.get('kontaktoplysninger_for_grundejer', {})
            
            # Tilføj udfylders kontaktinfo
            contact_info.append({
                'type': udfylder_rolle,
                'name': udfylder_info.get('name', '') or data.get('udfylder', ''),
                'company': udfylder_info.get('company', ''),
                'email': udfylder_info.get('email', ''),
                'phone': udfylder_info.get('phone', ''),
                'address': udfylder_info.get('address', ''),
                'city': udfylder_info.get('city', ''),
                'postal_code': udfylder_info.get('postal_code', '')
            })
            logger.info(f"Tilføjet {udfylder_rolle} kontakt (udfylder): {data.get('udfylder')}")
        
        # Håndter grundejer information når udfylder er Rådgiver eller Bygherre
        if udfylder_rolle in ['Rådgiver', 'Bygherre']:
            if udfylder_rolle == 'Bygherre':
                grundejer_info = data.get('hvem_er_grundejer_bygherre', {})
            else:
                grundejer_info = data.get('hvem_er_grundejer', {})
                
            if grundejer_info and any(grundejer_info.values()):
                contact_info.append({
                    'type': 'Grundejer',
                    'name': grundejer_info.get('name', ''),
                    'company': grundejer_info.get('company', ''),
                    'email': grundejer_info.get('email', ''),
                    'phone': grundejer_info.get('phone', ''),
                    'address': grundejer_info.get('address', ''),
                    'city': grundejer_info.get('city', ''),
                    'postal_code': grundejer_info.get('postal_code', '')
                })
                logger.info(f"Tilføjet grundejer kontakt: {grundejer_info.get('name')}")
        
        # Håndter rådgiver information for Bygherre og Grundejer
        has_external_consultant = False
        if udfylder_rolle == 'Bygherre':
            has_external_consultant = data.get('er_der_en_ekstern_konsulent_eller_raadgiver_tilknyttet_p_byg') == 'Ja'
            raadgiver_info = data.get('kontaktoplysninger_for_raadgiver_konsulent_byg', {})
        elif udfylder_rolle == 'Grundejer':
            has_external_consultant = data.get('er_der_en_ekstern_konsulent_eller_raadgiver_tilknyttet_projektet') == 'Ja'
            raadgiver_info = data.get('kontaktoplysninger_for_raadgiver', {})
            
        if has_external_consultant and raadgiver_info and any(raadgiver_info.values()):
            contact_info.append({
                'type': 'Rådgiver',
                'name': raadgiver_info.get('name', ''),
                'company': raadgiver_info.get('company', ''),
                'email': raadgiver_info.get('email', ''),
                'phone': raadgiver_info.get('phone', ''),
                'address': raadgiver_info.get('address', ''),
                'city': raadgiver_info.get('city', ''),
                'postal_code': raadgiver_info.get('postal_code', '')
            })
            logger.info(f"Tilføjet ekstern rådgiver kontakt: {raadgiver_info.get('name')}")
        
        # Udpak og forbered vedhæftede filer
        attachments = []
        
        # Håndter uploadede dokumenter
        if 'linked' in data and 'upload_dokumenter' in data['linked']:
            for doc_id, doc_info in data['linked']['upload_dokumenter'].items():
                attachments.append({
                    'file_name': doc_info.get('url', '').split('/')[-1],  # Brug original filnavn
                    'file_path': doc_info.get('url', '')
                })
                logger.info(f"Tilføjet vedhæftet fil: {doc_info.get('url', '').split('/')[-1]}")
        
        # Håndter samlet PDF
        if 'attachments' in data and 'attachments' in data['attachments']:
            att = data['attachments']['attachments']
            if 'url' in att:
                attachments.append({
                    'file_name': 'samlet_ansoegning.pdf',
                    'file_path': att['url']
                })
                logger.info("Tilføjet samlet ansøgning PDF")
        
        # Log hvad vi har udpakket
        logger.info(f"Udpakket data:\n" \
                   f"Submission: {submission_dict}\n" \
                   f"Adresser: {len(addresses)}\n" \
                   f"Kontakter: {len(contact_info)}\n" \
                   f"Vedhæftninger: {len(attachments)}")
        
        # Indsæt i database
        submission_id = db_handler.opret_submission(
            submission_data=submission_dict,
            addresses=addresses,
            contact_info=contact_info,
            attachments=attachments
        )
        
        return jsonify({
            'status': 'success',
            'message': 'Data modtaget og gemt',
            'submission_id': submission_id
        }), 200
        
    except Exception as e:
        app.logger.error(f"Fejl i webhook: {str(e)}")
        # Log stacktrace for bedre fejlfinding
        app.logger.error(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
