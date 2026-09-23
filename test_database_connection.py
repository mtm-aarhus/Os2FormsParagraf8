import os
import logging
import pyodbc
from database_handler import DatabaseHandler

# Konfigurer logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    try:
        # Opret en DatabaseHandler instans
        db_handler = DatabaseHandler(initialize_db=False)

        # Test databaseforbindelsen
        try:
            logging.info("Forsøger at oprette forbindelse til databasen...")
            conn_string = os.environ.get('SVAR_ASSIST_DB_CONNECTION')
            logging.info(f"Forbindelsesstreng starter med: {conn_string[:30] if conn_string else 'Ingen forbindelsesstreng fundet'}")
            if 'WEBSITE_SITE_NAME' in os.environ:
                logging.info("Kører i Azure - bruger Managed Identity autentificering")
            else:
                logging.info("Kører lokalt - bruger Windows-autentificering")
            with db_handler.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    row = cursor.fetchone()
                    logging.info(f"Test query result: {row[0]}")
            logging.info("Databaseforbindelse oprettet!")
        except Exception as e:
            logging.error(f"Fejl under test query: {e}")
    except Exception as e:
        logging.error(f"Fejl under test af databaseforbindelse: {e}")

if __name__ == "__main__":
    main()