"""The entry point of the process."""

from robot_framework import diagnostik
from robot_framework import queue_framework

# Diagnose-tilstand kortlaegger blankettens felter og skriver dem i loggen uden
# at roere koeen eller SharePoint. Se robot_framework/diagnostik.py.
if diagnostik.wanted():
    diagnostik.main()
else:
    queue_framework.main()
