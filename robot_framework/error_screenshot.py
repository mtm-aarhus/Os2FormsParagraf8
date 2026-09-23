"""This module has functionality to send error screenshots via smtp."""

import smtplib
from email.message import EmailMessage
import base64
import traceback
from io import BytesIO

from PIL import ImageGrab

from robot_framework import config


def send_error_screenshot(to_address: str | list[str], exception: Exception, process_name: str):
    """Sends an email with an error report, including a screenshot, when an exception occurs.
    Configuration details such as SMTP server, port, sender email, etc., should be set in 'config' module.

    Args:
        to_address: Email address or list of addresses to send the error report.
        exception: The exception that triggered the error.
        process_name: Name of the process from OpenOrchestrator.
    """
    # Create message
    msg = EmailMessage()
    msg['to'] = to_address
    msg['from'] = config.SCREENSHOT_SENDER
    msg['subject'] = f"Error screenshot: {process_name}"

    # Denne robot har ingen UI — et skaermbillede viser sjaeldent noget nyttigt, og
    # ImageGrab kan fejle helt hvis robotten koerer i en session uden skrivebord.
    # Fejlteksten er det vigtige, saa den sendes uanset om billedet lykkes.
    screenshot_html = ""
    try:
        screenshot = ImageGrab.grab()
        buffer = BytesIO()
        screenshot.save(buffer, format='PNG')
        screenshot_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        screenshot_html = f'<img src="data:image/png;base64,{screenshot_base64}" alt="Screenshot">'
    except Exception:  # pylint: disable=broad-exception-caught
        screenshot_html = "<p><i>Kunne ikke tage skaermbillede.</i></p>"

    # Create an HTML message with the exception and screenshot
    html_message = f"""
    <html>
        <body>
            <p>Error type: {type(exception).__name__}</p>
            <p>Error message: {exception}</p>
            <p>{traceback.format_exc()}</p>
            {screenshot_html}
        </body>
    </html>
    """

    msg.set_content("Please enable HTML to view this message.")
    msg.add_alternative(html_message, subtype='html')

    # Send message
    with smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT) as smtp:
        smtp.starttls()
        smtp.send_message(msg)
