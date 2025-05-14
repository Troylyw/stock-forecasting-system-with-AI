import json
import os
import openai # Keep for type hints if used, actual client created in methods
from log.custom_logger import log

# DEEPSEEK_BASE_URL can be a constant here
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"

# run_api is now instance method or part of Agent, Secretary will use its own.
# For Secretary's internal use (if any independent calls were made, though not apparent in original):
def _secretary_run_api(model, prompt, api_key, temperature: float = 0):
    if not api_key:
        log.logger.error("Secretary: DEEPSEEK_API_KEY not provided for API call.")
        return None
    try:
        client = openai.OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)
        response = client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": prompt}], temperature=temperature,
        )
        return response.choices[0].message.content
    except Exception as e:
        log.logger.error(f"Secretary: DeepSeek API Error: {e}")
        return None

class Secretary:
    def __init__(self, model: str, api_key: str): # Takes model and API key
        self.model = model
        self.api_key = api_key # Store API key
        log.logger.info(f"Secretary initialized with model: {self.model}")

    def get_response(self, prompt): # This could be used if Secretary makes its own calls
        log.logger.debug(f"Secretary sending prompt to model {self.model}: '{prompt[:100]}...'")
        response = _secretary_run_api(self.model, prompt, self.api_key) # Use stored key and model
        if response is None:
            log.logger.warning(f"Secretary received no response from _secretary_run_api for model {self.model}.")
            return "{}"
        log.logger.debug(f"Secretary received response: '{response[:100]}...'")
        return response

    # Added num_loan_types parameter for validation
    def check_loan(self, resp, max_loan, num_loan_types) -> (bool, str, dict):
        if not resp or not isinstance(resp, str):
            log.logger.debug(f"check_loan received invalid response: {resp}")
            return False, "Invalid or empty response from API.", {} # Return empty dict for loan
            
        if resp.count('{') == 1 and resp.count('}') == 1:
            start_idx = resp.index('{')
            end_idx = resp.index('}')
        else:
            fail_response = "Wrong json format, ensure LLM outputs only one JSON block: {}"
            log.logger.debug(fail_response.format(resp))
            return False, fail_response, {}

        action_json_str = resp[start_idx: end_idx + 1].replace("\n", "")
        try:
            parsed_json = json.loads(action_json_str)
        except json.JSONDecodeError as e:
            fail_response = f"Illegal json format: {e}. Ensure valid JSON."
            log.logger.error(f"{fail_response} String: '{action_json_str}'. Original: '{resp}'")
            return False, fail_response, {}

        try:
            if "loan" not in parsed_json:
                return False, "Key 'loan' not in response.", {}
            loan_decision = str(parsed_json["loan"]).lower()
            if loan_decision not in ["yes", "no"]:
                return False, "Value of key 'loan' should be 'yes' or 'no'.", {}
            parsed_json["loan"] = loan_decision

            if loan_decision == "no":
                if "loan_type" in parsed_json or "amount" in parsed_json:
                    return False, "Don't include loan_type or amount if 'loan' is no.", {}
                return True, "", parsed_json

            if loan_decision == "yes":
                if "loan_type" not in parsed_json or "amount" not in parsed_json:
                    return False, "Should include loan_type and amount if 'loan' is yes.", {}
                
                loan_type_val = parsed_json["loan_type"]
                # Validate loan_type_val is an int and within the range of available loan types (0 to num_loan_types-1)
                if not isinstance(loan_type_val, int) or not (0 <= loan_type_val < num_loan_types):
                    fail_msg = f"Value of key 'loan_type' should be an integer from 0 to {num_loan_types-1}."
                    return False, fail_msg, {}
                
                amount_val = parsed_json["amount"]
                if not (isinstance(amount_val, (int, float)) and 0 < amount_val <= max_loan):
                    fail_msg = f"Value of 'amount' should be a positive number <= max_loan ({max_loan})."
                    return False, fail_msg, {}
                parsed_json["amount"] = float(amount_val)
                return True, "", parsed_json
            
            log.logger.error(f"UNSOLVED LOAN JSON (logic error):{parsed_json}") # Should not be reached
            return False, "Internal logic error in loan checking.", {}
        except Exception as e: # Catch-all for unexpected errors during content validation
            log.logger.error(f"Unexpected error during loan content validation: {e}. JSON: {parsed_json}")
            return False, f"Unexpected validation error: {e}", {}


    def check_action(self, resp, cash, stock_a_amount, 
                     stock_b_amount, stock_a_price, stock_b_price) -> (bool, str, dict):
        if not resp or not isinstance(resp, str):
            return False, "Invalid or empty response from API.", {}

        if resp.count('{') == 1 and resp.count('}') == 1:
            start_idx, end_idx = resp.index('{'), resp.index('}')
        else:
            return False, "Wrong json format, ensure one JSON block: {}", {}
        
        action_json_str = resp[start_idx:end_idx+1].replace("\n", "")
        try:
            parsed_json = json.loads(action_json_str)
        except json.JSONDecodeError as e:
            return False, f"Illegal json format: {e}.", {}

        try:
            if "action_type" not in parsed_json: return False, "Key 'action_type' not in response.", {}
            action_type = str(parsed_json["action_type"]).lower()
            if action_type not in ["buy", "sell", "no"]:
                return False, "Value of 'action_type' must be 'buy', 'sell', or 'no'.", {}
            parsed_json["action_type"] = action_type

            if action_type == "no":
                if any(k in parsed_json for k in ["stock", "amount", "price"]):
                    return False, "Don't include stock, amount, or price if 'action_type' is no.", {}
                return True, "", parsed_json
            else: # buy or sell
                required = ["stock", "amount", "price"]
                if not all(k in parsed_json for k in required):
                    return False, f"Must include {', '.join(required)} for 'buy'/'sell'.", {}

                stock_id = str(parsed_json["stock"])
                if stock_id not in ['A', 'B']: return False, "Value of 'stock' must be 'A' or 'B'.", {}
                
                amount = parsed_json["amount"]
                if not (isinstance(amount, int) and amount > 0):
                    return False, "Value of 'amount' must be a positive integer.", {}

                price_llm = parsed_json["price"]
                if not (isinstance(price_llm, (int, float)) and price_llm > 0):
                    return False, "Value of 'price' must be a positive number.", {}

                transaction_value = amount * price_llm
                if action_type == "buy" and transaction_value > cash:
                    return False, f"Proposed buy ({transaction_value:.2f}) exceeds cash ({cash:.2f}).", {}
                
                if action_type == "sell":
                    holding = stock_a_amount if stock_id == 'A' else stock_b_amount
                    if amount > holding:
                        return False, f"Proposed sell ({amount}) exceeds holdings ({holding} of {stock_id}).", {}
                return True, "", parsed_json

            log.logger.error(f"UNSOLVED ACTION JSON (logic error):{parsed_json}") # Should not be reached
            return False, "Internal logic error in action checking.", {}
        except Exception as e:
            log.logger.error(f"Unexpected error during action content validation: {e}. JSON: {parsed_json}")
            return False, f"Unexpected validation error: {e}", {}


    def check_estimate(self, resp) -> (bool, str, dict):
        if not resp or not isinstance(resp, str):
            return False, "Invalid or empty response from API.", {}

        if resp.count('{') == 1 and resp.count('}') == 1:
            start_idx, end_idx = resp.index('{'), resp.index('}')
        else:
            return False, "Wrong json format, ensure one JSON block: {}", {}

        action_json_str = resp[start_idx:end_idx+1].replace("\n", "")
        try:
            parsed_json = json.loads(action_json_str)
        except json.JSONDecodeError as e:
            return False, f"Illegal json format: {e}.", {}

        try:
            expected_keys = ["buy_A", "buy_B", "sell_A", "sell_B", "loan"]
            if not all(k in parsed_json for k in expected_keys):
                return False, f"Expected keys missing. Need: {', '.join(expected_keys)}.", {}

            for key, value in parsed_json.items():
                if key not in expected_keys: # Should not happen if above check passes, but good for safety
                    return False, f"Unexpected key '{key}'.", {}
                value_str = str(value).lower()
                if value_str not in ['yes', 'no']:
                    return False, f"Value for '{key}' must be 'yes' or 'no'.", {}
                parsed_json[key] = value_str
            return True, "", parsed_json
        except Exception as e:
            log.logger.error(f"Unexpected error during estimate content validation: {e}. JSON: {parsed_json}")
            return False, f"Unexpected validation error: {e}", {}
