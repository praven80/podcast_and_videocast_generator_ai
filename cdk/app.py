from aws_cdk import App
from app_stack import AppStack

app = App()
AppStack(app, "AppStack1")
app.synth()