"""This module contains configuration constants used across the framework"""

# The number of times the robot retries on an error before terminating.
MAX_RETRY_COUNT = 3

# Whether the robot should be marked as failed if MAX_RETRY_COUNT is reached.
FAIL_ROBOT_ON_TOO_MANY_ERRORS = True

# Error screenshot config
SMTP_SERVER = "smtp.adm.aarhuskommune.dk"
SMTP_PORT = 25
SCREENSHOT_SENDER = "robot@friend.dk"

# Constant/Credential names
ERROR_EMAIL = "Error Email"


# OS2Forms
# ----------------------

# Credential i OpenOrchestrator — samme navn og facon som Os2FormsToSharepoint:
#   username = API base-URL (slutter paa /), password = API-noegle
OS2FORMS_CREDENTIAL = "OS2FormsAPI"

# Blankettens maskinnavn. Indgaar i URL'en som
#   {base_url}{webform_id}/submission/{uuid}
WEBFORM_ID = "paragraf_8_ansoegning"

# Hvor langt tilbage sikkerhedsnets-koerslen henter. Vinduet er bevidst meget
# bredere end koerselsintervallet: ansoegninger der allerede findes i SharePoint
# springes over paa dedup-feltet, saa overlap er gratis, mens et for smalt
# vindue ville tabe ansoegninger permanent hvis webhooken svigtede.
POLL_WINDOW_DAYS = 14


# SharePoint
# ----------------------

# Credentials i OpenOrchestrator — samme navne som de oevrige MTM-robotter:
#   SharePointAPI   username = tenant,    password = client id
#   SharePointCert  username = thumbprint, password = sti til .pem
SHAREPOINT_API_CREDENTIAL = "SharePointAPI"
SHAREPOINT_CERT_CREDENTIAL = "SharePointCert"

# Constant med base-URL'en; sitets sti saettes bagefter.
SHAREPOINT_BASE_CONSTANT = "AarhusKommuneSharePoint"
SHAREPOINT_SITE_PATH = "/Teams/tea-teamsiteXXXXX"  # TODO: udfyldes naar sitet er valgt

# Listenavne. Skal matche SHAREPOINT-LISTER.md praecist.
LIST_ANSOGNINGER = "P8Ansogninger"
LIST_ADRESSER = "P8Adresser"
LIST_KONTAKTER = "P8Kontakter"
LIST_VEDHAEFTNINGER = "P8Vedhaeftninger"

# Feltet der bruges til dubletfiltrering. Bemaerk at dette er det INTERNE
# kolonnenavn — se "Interne kolonnenavne" i SHAREPOINT-LISTER.md.
DEDUP_FIELD = "SubmissionUUID"


# Queue specific configs
# ----------------------

# The name of the job queue (if any)
QUEUE_NAME = "Paragraf8Ansogninger"

# The limit on how many queue elements to process
MAX_TASK_COUNT = 100

# ----------------------
