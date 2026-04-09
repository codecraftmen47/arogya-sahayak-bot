from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
import requests
import os

class ActionQueryVaccineCenters(Action):
    def name(self) -> str:
        return "action_query_vaccine_centers"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        pin_code = tracker.get_slot("pin_code")
        date = tracker.get_slot("date")

        url = f"https://cdn-api.co-vin.in/api/v2/appointment/sessions/public/findByPin?pincode={pin_code}&date={date}"
        headers = {"User-Agent": "Mozilla/5.0"}

        try:
            response = requests.get(url, headers=headers)
            data = response.json()
            sessions = data.get('sessions', [])
            if sessions:
                message = "Vaccination centers available:\n"
                for session in sessions[:3]:
                    message += f"- {session['name']}, Fee: {session['fee_type']}\n"
                dispatcher.utter_message(text=message)
            else:
                dispatcher.utter_message(text="No centers found for this date. Please try a different date or pincode.")
        except requests.exceptions.RequestException:
            dispatcher.utter_message(text="Sorry, I couldn't connect to the vaccine database right now. Please try again later.")

        return []

class ActionCheckSymptoms(Action):
    def name(self) -> str:
        return "action_check_symptoms"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        symptom = tracker.get_slot("symptom")
        # Simple symptom checker logic - would be expanded with real medical data
        if "fever" in symptom.lower() or "bukhar" in symptom.lower():
            dispatcher.utter_message(text="For fever, rest and hydrate. If it persists for more than 2 days or is very high, please contact a health worker.")
        elif "cough" in symptom.lower() or "khansi" in symptom.lower():
            dispatcher.utter_message(text="For cough, avoid cold drinks. If accompanied by fever or breathing difficulty, seek medical advice.")
        else:
            dispatcher.utter_message(text="I understand you're not feeling well. For more specific advice, please describe your main symptom in more detail.")
        return []