"""
PersonaPlex integration

Drone speaks instructions when a visual target is detected, or when a task is assigned. 
This can be used for debugging, or for user feedback in a real deployment.
"""

import pyttsx3

class VoiceAgent:
    def __init__(self, voice_id=None):
        self.engine = pyttsx3.init()
        if voice_id is not None:
            self.engine.setProperty('voice', voice_id)

    def speak(self, text):
        self.engine.say(text)
        self.engine.runAndWait()