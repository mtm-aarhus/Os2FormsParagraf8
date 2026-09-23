import os
import time
import random
import logging
import sys
from contextlib import contextmanager
from typing import Dict, List, Optional, Union
from urllib.parse import urlparse, parse_qs
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool

# Konfiguration
POOL_SIZE = 5
CONNECTION_TIMEOUT = 30
COMMAND_TIMEOUT = 30

# Ingen global kode her, der forsøger at initialisere databasen

def convert_sqlalchemy_to_odbc(sqlalchemy_url):
    """Konverterer en SQLAlchemy URL til en ODBC forbindelsesstreng."""
    logger = logging.getLogger("DatabaseHandler")
    logger.info(f"Konverterer SQLAlchemy URL: {sqlalchemy_url[:20]}...")
    
    parsed = urlparse(sqlalchemy_url)
    params = parse_qs(parsed.query)
    
    # Udpak parametre
    server = parsed.netloc
    database = parsed.path.lstrip('/')
    logger.info(f"Server: {server}, Database: {database}")
    
    # Få driver fra URL eller brug ODBC Driver 18 som default
    driver = params.get('driver', ['ODBC Driver 18 for SQL Server'])[0]
    driver = driver.replace('+', ' ')  # Konverter URL-encoded spaces
    logger.info(f"Driver: {driver}")
    
    # Byg forbindelsesstreng med nøjagtig de samme parametre som i Streamlit appen
    conn_string = (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        "Authentication=ActiveDirectoryMsi;"
        "Encrypt=yes;"
        "TrustServerCertificate=no"
    )
    
    logger.info(f"Konverteret forbindelsesstreng: {conn_string[:50]}...")
    return conn_string


def validate_connection_string(conn_string):
    """Validerer at forbindelsesstrengen indeholder de nødvendige komponenter."""
    if not conn_string:
        raise ValueError("Forbindelsesstrengen er tom eller None. Sørg for at 'SVAR_ASSIST_DB_CONNECTION' miljøvariablen er sat.")

    # Log forbindelsesstrengen (uden at vise hele indholdet)
    logger = logging.getLogger("DatabaseHandler")
    safe_conn_string = conn_string[:20] + '...' if len(conn_string) > 20 else conn_string
    logger.info(f"Validerer forbindelsesstreng: {safe_conn_string}")

    if 'mssql+pyodbc://' in conn_string:
        try:
            logger.info("Konverterer SQLAlchemy URL til ODBC format")
            conn_string = convert_sqlalchemy_to_odbc(conn_string)
            logger.info("Konvertering gennemført")
        except Exception as e:
            logger.error(f"Kunne ikke konvertere SQLAlchemy URL til ODBC format: {str(e)}")
            raise ValueError(f"Kunne ikke konvertere SQLAlchemy URL til ODBC format: {str(e)}")

    required_components = ["driver", "server", "database"]
    for component in required_components:
        if component not in conn_string.lower():
            logger.error(f"'{component}' mangler i forbindelsesstrengen")
            raise ValueError(f"'{component}' mangler i forbindelsesstrengen")
    
    # Log success
    logger.info("Forbindelsesstreng valideret")
    return conn_string


def test_network_connectivity(host, port=1433):
    """Tester netværksforbindelsen til en server."""
class DatabaseHandler:
    def __init__(self, initialize_db=True):
        self.logger = logging.getLogger("DatabaseHandler")
        self.logger.setLevel(logging.INFO)
        self._cached_engine = None
        
        # Tjek om vi kører i Azure
        is_azure_environment = bool(os.environ.get('WEBSITE_SITE_NAME'))
        
        # Hent forbindelsesstrengen
        conn_string = os.environ.get('SVAR_ASSIST_DB_CONNECTION', '')
        self.logger.info(f"Rå forbindelsesstreng fra miljøvariabel: {conn_string[:20]}...")
        
        # Fjern eventuelle 'SVAR_ASSIST_DB_CONNECTION=' præfikser (kan ske i Azure)
        prefix = 'SVAR_ASSIST_DB_CONNECTION='
        if conn_string.startswith(prefix):
            self.logger.info(f"Fjerner '{prefix}' præfiks fra forbindelsesstrengen")
            conn_string = conn_string[len(prefix):]
        
        # Fjern whitespace og anførselstegn
        conn_string = conn_string.strip().strip('"\'')
        
        # Valider at forbindelsesstrengen starter med korrekt protokol
        if not conn_string.startswith('mssql+pyodbc://'):
            self.logger.error(f"Ugyldig forbindelsesstreng protokol: {conn_string[:20]}...")
            raise ValueError("Forbindelsesstrengen skal starte med 'mssql+pyodbc://'")
        
        self.logger.info(f"Behandlet forbindelsesstreng: {conn_string[:20]}...")
        
        # Hvis vi ikke har en forbindelsesstreng, opret standard
        if not conn_string:
            if is_azure_environment:
                self.logger.info("Opretter MSI connection string for Azure")
                conn_string = (
                    "mssql+pyodbc://"
                    "svarassist.database.windows.net:1433"
                    "/Paragraf_8_Ansogning"
                    "?driver=ODBC+Driver+18+for+SQL+Server"
                    "&authentication=ActiveDirectoryMsi"
                    "&encrypt=yes"
                    "&trustservercertificate=no"
                )
            else:
                self.logger.info("Opretter connection string for lokal udvikling")
                conn_string = (
                    "mssql+pyodbc://"
                    "svarassist.database.windows.net:1433"
                    "/Paragraf_8_Ansogning"
                    "?driver=ODBC+Driver+18+for+SQL+Server"
                    "&authentication=ActiveDirectoryInteractive"
                    "&encrypt=yes"
                    "&trustservercertificate=no"
                )
        
        self.conn_string = conn_string
        
        # Log maskeret forbindelsesstreng
        masked_conn = self.conn_string
        if 'authentication=ActiveDirectoryMsi' in masked_conn.lower():
            masked_conn = masked_conn.replace('ActiveDirectoryMsi', '***MSI***')
        elif 'authentication=ActiveDirectoryInteractive' in masked_conn.lower():
            masked_conn = masked_conn.replace('ActiveDirectoryInteractive', '***Interactive***')
        self.logger.info(f"Bruger connection string: {masked_conn}")
        
        # Opret SQLAlchemy engine med connection pooling
        try:
            self.engine = create_engine(
                self.conn_string,
                poolclass=QueuePool,
                pool_size=POOL_SIZE,
                pool_timeout=CONNECTION_TIMEOUT,
                pool_recycle=3600,  # Genopret forbindelser efter en time
                connect_args={"timeout": COMMAND_TIMEOUT}
            )
            
            # Test forbindelsen
            self.test_connection()
            self.logger.info("Database forbindelse oprettet succesfuldt")
            
            # Initialiser database hvis nødvendigt
            if initialize_db:
                try:
                    self.initialize_database()
                except Exception as e:
                    self.logger.error(f"Fejl ved initialisering af database: {str(e)}")
                    self.logger.error("Fortsætter uden databaseinitialisering")
                    
        except Exception as e:
            self.logger.error(f"Fejl ved oprettelse af database forbindelse: {str(e)}")
            if is_azure_environment:
                self.logger.error("MSI autentifikation fejlede i Azure miljø. Tjek Managed Identity konfiguration.")
                self.logger.error("Tjek også at SQL Server firewall tillader Azure tjenester.")
            raise

    def log_info(self, message):
        self.logger.info(message)

    def log_error(self, message):
        self.logger.error(message)

    def log_trace(self, message):
        self.logger.debug(message)

    def initialize_database(self):
        """Initialiserer databasen med nødvendige tabeller."""
        self.logger.info("Initialiserer database struktur...")
        
        try:
            with self.get_connection() as conn:
                # Tjek om tabellerne eksisterer
                result = conn.execute(text("""
                    SELECT COUNT(*) 
                    FROM INFORMATION_SCHEMA.TABLES 
                    WHERE TABLE_NAME IN ('submissions', 'addresses', 'contact_info', 'attachments')
                """))
                table_count = result.scalar()
                
                if table_count == 4:
                    self.logger.info("Alle nødvendige tabeller eksisterer")
                    return

                # Opret submissions tabel
                conn.execute(text("""
                    IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'submissions')
                    CREATE TABLE submissions (
                        id INT IDENTITY(1,1) PRIMARY KEY,
                        udfylder NVARCHAR(255) NOT NULL,
                        vaelg_dato_for_ansoegning DATE NOT NULL,
                        bemaerkninger NVARCHAR(MAX),
                        udfylder_rolle NVARCHAR(50) NOT NULL,
                        status BIT DEFAULT 1,
                        decision_written BIT DEFAULT 0
                    )
                """))

                # Opret addresses tabel
                conn.execute(text("""
                    IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'addresses')
                    CREATE TABLE addresses (
                        id INT IDENTITY(1,1) PRIMARY KEY,
                        submission_id INT NOT NULL,
                        lokalitets_nummer NVARCHAR(50),
                        mat NVARCHAR(255),
                        vaelg_adresse NVARCHAR(255),
                        FOREIGN KEY (submission_id) REFERENCES submissions(id)
                    )
                """))

                # Opret contact_info tabel
                conn.execute(text("""
                    IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'contact_info')
                    CREATE TABLE contact_info (
                        id INT IDENTITY(1,1) PRIMARY KEY,
                        submission_id INT NOT NULL,
                        type NVARCHAR(50) NOT NULL,
                        name NVARCHAR(255),
                        company NVARCHAR(255),
                        email NVARCHAR(255),
                        phone NVARCHAR(50),
                        address NVARCHAR(255),
                        city NVARCHAR(100),
                        postal_code NVARCHAR(20),
                        FOREIGN KEY (submission_id) REFERENCES submissions(id)
                    )
                """))

                # Opret attachments tabel
                conn.execute(text("""
                    IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'attachments')
                    CREATE TABLE attachments (
                        id INT IDENTITY(1,1) PRIMARY KEY,
                        submission_id INT NOT NULL,
                        file_name NVARCHAR(255),
                        file_path NVARCHAR(MAX),
                        FOREIGN KEY (submission_id) REFERENCES submissions(id)
                    )
                """))
                
                conn.commit()
                self.logger.info("Database struktur initialiseret succesfuldt")
                
        except Exception as e:
            self.logger.error(f"Fejl ved initialisering af database struktur: {str(e)}")
            raise

    def opret_submission(self, submission_data: Dict, addresses: List[Dict], attachments: List[Dict], contact_info: List[Dict]) -> int:
        """
        Opret en submission med tilhørende adresser, kontaktoplysninger og vedhæftede filer.
        """
        try:
            with self.get_connection() as conn:
                # Indsæt submission
                result = conn.execute(text("""
                    INSERT INTO submissions (
                        udfylder, vaelg_dato_for_ansoegning, 
                        bemaerkninger, udfylder_rolle, status, decision_written
                    )
                    OUTPUT INSERTED.id
                    VALUES (
                        :udfylder, :dato, 
                        :bemaerkninger, :rolle, :status, :decision_written
                    )
                """), {
                    "udfylder": submission_data["udfylder"],
                    "dato": submission_data["vaelg_dato_for_ansoegning"],
                    "bemaerkninger": submission_data.get("bemaerkninger"),
                    "rolle": submission_data["udfylder_rolle"],
                    "status": True,  # Ny submission er altid aktiv
                    "decision_written": submission_data.get("decision_written", False)
                })
                
                submission_id = result.scalar()
                self.log_info(f"Submission oprettet med ID: {submission_id}")

                # Indsæt adresser
                for address in addresses:
                    self.log_trace(f"Indsætter adresse: {address}")
                    conn.execute(text("""
                        INSERT INTO addresses (submission_id, vaelg_adresse, mat, lokalitets_nummer)
                        VALUES (:submission_id, :adresse, :mat, :lokalitet)
                    """), {
                        "submission_id": submission_id,
                        "adresse": address.get("vaelg_adresse"),
                        "mat": address.get("mat"),
                        "lokalitet": address.get("lokalitets_nummer")
                    })
                
                # Indsæt kontaktoplysninger
                for contact in contact_info:
                    self.log_trace(f"Indsætter kontaktoplysning: {contact}")
                    conn.execute(text("""
                        INSERT INTO contact_info (
                            submission_id, type, name, company, email, 
                            phone, address, city, postal_code
                        )
                        VALUES (
                            :submission_id, :type, :name, :company, :email,
                            :phone, :address, :city, :postal_code
                        )
                    """), {
                        "submission_id": submission_id,
                        "type": contact.get("type"),
                        "name": contact.get("name"),
                        "company": contact.get("company"),
                        "email": contact.get("email"),
                        "phone": contact.get("phone"),
                        "address": contact.get("address"),
                        "city": contact.get("city"),
                        "postal_code": contact.get("postal_code")
                    })

                # Indsæt vedhæftninger
                for attachment in attachments:
                    self.log_trace(f"Indsætter vedhæftning: {attachment.get('file_name')}")
                    conn.execute(text("""
                        INSERT INTO attachments (submission_id, file_name, file_path)
                    VALUES (:submission_id, :file_name, :file_path)
                """), {
                    "submission_id": submission_id,
                    "file_name": attachment.get("file_name"),
                    "file_path": attachment.get("file_path")
                    })

                conn.commit()
                return submission_id

        except Exception as e:
            if conn and not conn.closed:
                try:
                    conn.rollback()
                except Exception as rollback_error:
                    self.log_error(f"Fejl ved rollback: {str(rollback_error)}")
            self.log_error(f"Fejl ved oprettelse af submission: {str(e)}")
            raise

    @contextmanager
    def verify_database_access(self):
        """Verificerer at den aktuelle identity har adgang til databasen."""
        try:
            # Brug en simpel forbindelsesstreng uden database
            server = self.conn_string.split('SERVER=')[1].split(';')[0]
            conn_string = f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={server};Authentication=ActiveDirectoryMsi;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
            
            self.logger.info("Tester database adgang...")
            conn = pyodbc.connect(conn_string)
            cursor = conn.cursor()
            
            # Test forbindelse og bruger
            cursor.execute("SELECT CURRENT_USER, USER_NAME()")
            current_user, user_name = cursor.fetchone()
            self.logger.info(f"Forbundet som: {current_user} / {user_name}")
            
            # Test rettigheder
            cursor.execute("""
                SELECT HAS_PERMS_BY_NAME(NULL, 'DATABASE', 'CONNECT') as can_connect,
                       HAS_PERMS_BY_NAME(NULL, 'DATABASE', 'CREATE TABLE') as can_create_table
            """)
            permissions = cursor.fetchone()
            self.logger.info(f"Rettigheder: CONNECT={permissions[0]}, CREATE TABLE={permissions[1]}")
            
            cursor.close()
            conn.close()
            return True
        except Exception as e:
            self.logger.error(f"Kunne ikke verificere database adgang: {str(e)}")
            return False
    
    def get_engine(self):
        """Henter cached database engine eller opretter en ny"""
        if self._cached_engine is None:
            self.logger.info("Opretter ny database engine")
            start_time = time.time()
            self._cached_engine = create_engine(self.conn_string)
            self.logger.info(f"Ny engine oprettet på {time.time() - start_time:.2f} sekunder")
        return self._cached_engine

    def test_connection(self):
        """Tester database forbindelsen"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                result.fetchone()
                self.logger.info("Database forbindelse testet succesfuldt")
                return True
        except Exception as e:
            self.logger.error(f"Fejl ved test af forbindelse: {str(e)}")
            raise

    @contextmanager
    def get_connection(self, max_retries=2, initial_backoff=1, max_backoff=10):
        """Returnerer en database forbindelse med retry logik"""
        retries = 0
        last_exception = None
        backoff = initial_backoff
        
        while retries <= max_retries:
            conn = None
            try:
                conn = self.engine.connect()
                yield conn
                conn.close()
                break  # Hvis vi når hertil uden exceptions, break ud af while-loopen
            except Exception as e:
                if conn is not None:
                    try:
                        conn.close()
                    except:
                        pass  # Ignorer fejl ved lukning af forbindelse
                
                last_exception = e
                retries += 1
                
                if retries <= max_retries:
                    self.logger.warning(f"Forbindelsesfejl: {str(e)}. Forsøger igen ({retries}/{max_retries}) om {backoff} sekunder...")
                    jitter = random.uniform(0, 0.1 * backoff)
                    time.sleep(backoff + jitter)
                    backoff = min(backoff * 2, max_backoff)
                else:
                    self.logger.error(f"Kunne ikke oprette forbindelse efter {max_retries} forsøg: {str(e)}")
                    raise last_exception
                    
    def gem_webhook_data(self, json_data):
        """Gemmer rå webhook data i webhook_data tabellen."""
        with self.get_connection() as conn:
            # Opret webhook_data tabellen hvis den ikke findes
            conn.execute(text("""
                IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'webhook_data')
                BEGIN
                    CREATE TABLE webhook_data (
                        id INT IDENTITY(1,1) PRIMARY KEY,
                        received_at DATETIME DEFAULT GETDATE(),
                        data NVARCHAR(MAX)
                    )
                END
            """))
            
            # Gem JSON data
            conn.execute(
                text("INSERT INTO webhook_data (data) VALUES (:json_data)"),
                {"json_data": json_data}
            )
            
            conn.commit()
