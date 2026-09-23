"""This module contains configuration constants used across the framework"""

# The number of times the robot retries on an error before terminating.
MAX_RETRY_COUNT = 3

# Whether the robot should be marked as failed if MAX_RETRY_COUNT is reached.
FAIL_ROBOT_ON_TOO_MANY_ERRORS = True

# Error screenshot config
SMTP_SERVER = "smtp.aarhuskommune.local"
SMTP_PORT = 25
SCREENSHOT_SENDER = "robot@friend.dk"

# Constant/Credential names
ERROR_EMAIL = "Error Email"


# OS2Forms
# ----------------------

# Credential i OpenOrchestrator. Vaerdien laegges i password-feltet;
# username bruges ikke af OS2Forms' api-key-header.
OS2FORMS_CREDENTIAL = "OS2FormsApiKey"

# Constants i OpenOrchestrator.
OS2FORMS_BASE_URL_CONSTANT = "os2forms_base_url"
OS2FORMS_WEBFORM_ID_CONSTANT = "paragraf8_webform_id"

# Hvor langt tilbage der hentes ved hver koersel. Vinduet er bevidst meget
# bredere end koerselsintervallet: submissions der allerede findes i SharePoint
# springes over paa SubmissionUUID, saa overlap er gratis, mens et for smalt
# vindue ville tabe ansoegninger permanent hvis en koersel fejlede.
POLL_WINDOW_DAYS = 14


# SharePoint
# ----------------------

# Credentials i OpenOrchestrator — samme moenster som Aktivtsystem_ejerskab.
SHAREPOINT_API_CREDENTIAL = "SharePointAPI"    # username=tenant-id, password=client-id
SHAREPOINT_CERT_CREDENTIAL = "SharePointCert"  # username=thumbprint, password=sti til .pem

# Constant i OpenOrchestrator med site-URL'en.
SHAREPOINT_URL_CONSTANT = "paragraf8_sharepoint"

# Listenavne. Skal matche SHAREPOINT-LISTER.md praecist.
LIST_ANSOGNINGER = "P8Ansogninger"
LIST_ADRESSER = "P8Adresser"
LIST_KONTAKTER = "P8Kontakter"
LIST_VEDHAEFTNINGER = "P8Vedhaeftninger"


# Queue specific configs
# ----------------------

# The name of the job queue (if any)
QUEUE_NAME = "Paragraf8Ansogninger"

# The limit on how many queue elements to process
MAX_TASK_COUNT = 100

# ----------------------
