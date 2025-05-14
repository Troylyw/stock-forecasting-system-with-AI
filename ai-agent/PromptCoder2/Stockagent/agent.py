import math
import time
import openai
# import tiktoken # Not actively used
import random
# import requests # Not used

# import util # We'll get values from config passed to __init__
from log.custom_logger import log

from prompt.agent_prompt import *
from procoder.functional import format_prompt
from procoder.prompt import *
from secretary import Secretary # Secretary is passed in
# from stock import Stock # Stock instances are passed in for plan_stock

# random_init needs access to config values previously from util
def random_init(stock_a_initial, stock_b_initial, config): # Added config
    stock_a, stock_b, cash, debt_amount = 0.0, 0.0, 0.0, 0.0
    # Use config values
    min_initial_prop = config['MIN_INITIAL_PROPERTY']
    max_initial_prop = config['MAX_INITIAL_PROPERTY']

    while stock_a * stock_a_initial + stock_b * stock_b_initial + cash < min_initial_prop \
            or stock_a * stock_a_initial + stock_b * stock_b_initial + cash > max_initial_prop \
            or debt_amount > stock_a * stock_a_initial + stock_b * stock_b_initial + cash:
        stock_a = int(random.uniform(0, max_initial_prop / stock_a_initial if stock_a_initial > 0 else max_initial_prop))
        stock_b = int(random.uniform(0, max_initial_prop / stock_b_initial if stock_b_initial > 0 else max_initial_prop))
        cash = random.uniform(0, max_initial_prop)
        debt_amount = random.uniform(0, max_initial_prop)
    
    debt = {
        "loan": "yes",
        "amount": debt_amount,
        "loan_type": random.randint(0, len(config['LOAN_TYPE']) - 1), # Use config
        "repayment_date": random.choice(config['REPAYMENT_DAYS']) # Use config
    }
    return stock_a, stock_b, cash, debt


class Agent:
    def __init__(self, i, stock_a_price, stock_b_price, secretary: Secretary, model: str, config: dict): # Added config
        self.order = i
        self.secretary = secretary # Secretary now handles its own API key
        self.model = model # Passed from main, originally from config
        self.config = config # Store config for later use by methods

        self.character = random.choice(["Conservative", "Aggressive", "Balanced", "Growth-Oriented"])

        # Pass config to random_init
        self.stock_a_amount, self.stock_b_amount, self.cash, init_debt = random_init(stock_a_price, stock_b_price, config)
        self.init_proper = self.get_total_proper(stock_a_price, stock_b_price)

        self.action_history = [[] for _ in range(config['TOTAL_DATE'])] # Use config
        self.chat_history = []
        self.loans = [init_debt]
        self.is_bankrupt = False
        self.quit = False
        
        # Store current loan rates, can be updated by events
        self.current_loan_rates = list(self.config['LOAN_RATE'])
        self.api_key = config['DEEPSEEK_API_KEY'] # Store API key

    def update_loan_rates(self, new_rates):
        self.current_loan_rates = list(new_rates)
        log.logger.info(f"Agent {self.order}: Loan rates updated to {self.current_loan_rates}")

    def run_api(self, prompt, temperature: float = 1):
        return self.run_api_deepseek(prompt, temperature) # Changed name for clarity

    def run_api_deepseek(self, prompt, temperature: float = 1):
        if not self.api_key: # Use stored API key
            log.logger.error("ERROR: DEEPSEEK_API_KEY not found in agent's config.")
            return ""

        try:
            client = openai.OpenAI(
                api_key=self.api_key, # Use stored API key
                base_url="https://api.deepseek.com/v1"
            )
        except Exception as e:
            log.logger.error(f"Error initializing OpenAI client for DeepSeek: {e}")
            return ""

        self.chat_history.append({"role": "user", "content": prompt})
        max_retry = 2
        retry = 0

        while retry < max_retry:
            try:
                response = client.chat.completions.create(
                    model=self.model, # Use agent's model
                    messages=self.chat_history,
                    temperature=temperature,
                )
                msg = response.choices[0].message
                if msg and msg.content is not None:
                    self.chat_history.append({"role": msg.role, "content": msg.content})
                    return msg.content
                else:
                    log.logger.warning(f"DeepSeek API returned an empty message or content for prompt: {prompt}")
                    if msg is None: log.logger.warning("response.choices[0].message was None.")
                    elif msg.content is None: log.logger.warning("response.choices[0].message.content was None.")
                    raise openai.APIError("Received empty message content from DeepSeek.", response=response, body=None) # type: ignore
            except openai.APIError as e:
                log.logger.warning(f"DeepSeek API Error (APIError), retry {retry+1}/{max_retry}: {e}")
                retry += 1
                time.sleep(1)
            except openai.OpenAIError as e:
                log.logger.warning(f"DeepSeek API Error (OpenAIError), retry {retry+1}/{max_retry}: {e}")
                retry += 1
                time.sleep(1)
            except Exception as e:
                log.logger.error(f"Unexpected error during DeepSeek API call, retry {retry+1}/{max_retry}: {e}")
                retry += 1
                time.sleep(1)

        log.logger.error(f"ERROR: DeepSeek API FAILED AFTER {max_retry} RETRIES. SKIP THIS INTERACTION.")
        return ""

    def get_total_proper(self, stock_a_price, stock_b_price):
        return (self.stock_a_amount * stock_a_price +
                self.stock_b_amount * stock_b_price +
                self.cash)

    def get_proper_cash_value(self, stock_a_price, stock_b_price):
        proper = self.get_total_proper(stock_a_price, stock_b_price)
        a_value = self.stock_a_amount * stock_a_price
        b_value = self.stock_b_amount * stock_b_price
        return proper, self.cash, a_value, b_value

    def get_total_loan(self):
        return sum(loan["amount"] for loan in self.loans)

    def plan_loan(self, date, stock_a_price, stock_b_price, lastday_forum_message):
        if self.quit:
            return {"loan": "no"}

        # Use self.current_loan_rates which reflects event changes
        loan_rate1 = self.current_loan_rates[0] if len(self.current_loan_rates) > 0 else 0
        loan_rate2 = self.current_loan_rates[1] if len(self.current_loan_rates) > 1 else 0
        loan_rate3 = self.current_loan_rates[2] if len(self.current_loan_rates) > 2 else 0
        
        if date == 1:
            prompt_template = Collection(
                BACKGROUND_PROMPT, LOAN_TYPE_PROMPT, DECIDE_IF_LOAN_PROMPT
            ).set_indexing_method(sharp2_indexing).set_sep("\n")
            max_loan = self.init_proper - self.get_total_loan() # Max loan could be a % of property
            inputs = {
                'date': date, 'character': self.character,
                'stock_a': self.stock_a_amount, 'stock_b': self.stock_b_amount,
                'cash': self.cash, 'debt': self.loans, 'max_loan': max_loan,
                'loan_rate1': loan_rate1, 'loan_rate2': loan_rate2, 'loan_rate3': loan_rate3,
                'loan_type_names': ", ".join(self.config['LOAN_TYPE']), # Provide loan type names
                'loan_type_durations': ", ".join(map(str, self.config['LOAN_TYPE_DATE'])) # And durations
            }
        else:
            prompt_template = Collection(
                BACKGROUND_PROMPT, LASTDAY_FORUM_AND_STOCK_PROMPT,
                LOAN_TYPE_PROMPT, DECIDE_IF_LOAN_PROMPT
            ).set_indexing_method(sharp2_indexing).set_sep("\n")
            max_loan = self.get_total_proper(stock_a_price, stock_b_price) * 0.5 - self.get_total_loan() # Example: max loan 50% of current property minus existing debt
            inputs = {
                "date": date, "character": self.character,
                "stock_a": self.stock_a_amount, "stock_b": self.stock_b_amount,
                "cash": self.cash, "debt": self.loans, "max_loan": max_loan,
                "stock_a_price": stock_a_price, "stock_b_price": stock_b_price,
                "lastday_forum_message": lastday_forum_message,
                'loan_rate1': loan_rate1, 'loan_rate2': loan_rate2, 'loan_rate3': loan_rate3,
                'loan_type_names': ", ".join(self.config['LOAN_TYPE']),
                'loan_type_durations': ", ".join(map(str, self.config['LOAN_TYPE_DATE']))
            }

        if max_loan <= 0:
            log.logger.info(f"Agent {self.order}: Max loan is {max_loan}, deciding not to loan without API call.")
            return {"loan": "no"}

        try_times = 0
        MAX_TRY_TIMES = 3
        resp = self.run_api(format_prompt(prompt_template, inputs))
        if resp == "": return {"loan": "no"}

        # Secretary's check_loan needs max_loan and number of loan types for validation
        loan_format_check, fail_response, loan = self.secretary.check_loan(resp, max_loan, len(self.config['LOAN_TYPE']))
        while not loan_format_check:
            try_times += 1
            if try_times > MAX_TRY_TIMES:
                log.logger.warning(f"Agent {self.order}: Loan format try times > MAX_TRY_TIMES. Skip as no loan today.")
                loan = {"loan": "no"}; break
            resp = self.run_api(format_prompt(LOAN_RETRY_PROMPT, {"fail_response": fail_response}))
            if resp == "": loan = {"loan": "no"}; break
            loan_format_check, fail_response, loan = self.secretary.check_loan(resp, max_loan, len(self.config['LOAN_TYPE']))

        if loan.get("loan") == "yes":
            loan_type_idx = loan.get("loan_type") # This is an index 0, 1, 2
            # Use config for LOAN_TYPE_DATE
            if loan_type_idx is not None and 0 <= loan_type_idx < len(self.config['LOAN_TYPE_DATE']):
                loan["repayment_date"] = date + self.config['LOAN_TYPE_DATE'][loan_type_idx]
                self.loans.append(loan)
                self.cash += loan["amount"]
                log.logger.info(f"INFO: Agent {self.order} decide to loan: {loan}")
            else:
                log.logger.warning(f"Agent {self.order}: Invalid loan_type index {loan_type_idx} in loan decision. Not taking loan.")
                loan = {"loan": "no"}
        else:
            log.logger.info(f"INFO: Agent {self.order} decide not to loan")
        return loan

    def plan_stock(self, date, time, stock_a, stock_b, stock_a_deals, stock_b_deals): # stock_a, stock_b are Stock objects
        if self.quit: return {"action_type": "no"}

        prompt_template = None
        # Use config for SEASON_REPORT_DAYS
        if date in self.config['SEASON_REPORT_DAYS'] and time == 1:
            index = self.config['SEASON_REPORT_DAYS'].index(date)
            prompt_template = Collection(
                FIRST_DAY_FINANCIAL_REPORT, FIRST_DAY_BACKGROUND_KNOWLEDGE,
                SEASONAL_FINANCIAL_REPORT, DECIDE_BUY_STOCK_PROMPT
            ).set_indexing_method(sharp2_indexing).set_sep("\n")
            inputs = {
                "date": date, "time": time,
                "stock_a": self.stock_a_amount, "stock_b": self.stock_b_amount,
                "stock_a_price": stock_a.get_price(), "stock_b_price": stock_b.get_price(),
                "stock_a_deals": stock_a_deals, "stock_b_deals": stock_b_deals,
                "cash": self.cash,
                # Stock object's gen_financial_report will use its internally stored config
                "stock_a_report": stock_a.gen_financial_report(index),
                "stock_b_report": stock_b.gen_financial_report(index)
            }
        elif time == 1:
            prompt_template = Collection(
                FIRST_DAY_FINANCIAL_REPORT, FIRST_DAY_BACKGROUND_KNOWLEDGE, DECIDE_BUY_STOCK_PROMPT
            ).set_indexing_method(sharp2_indexing).set_sep("\n")
            inputs = {
                "date": date, "time": time,
                "stock_a": self.stock_a_amount, "stock_b": self.stock_b_amount,
                "stock_a_price": stock_a.get_price(), "stock_b_price": stock_b.get_price(),
                "stock_a_deals": stock_a_deals, "stock_b_deals": stock_b_deals, "cash": self.cash
            }
        else:
            prompt_template = DECIDE_BUY_STOCK_PROMPT
            inputs = {
                "date": date, "time": time,
                "stock_a": self.stock_a_amount, "stock_b": self.stock_b_amount,
                "stock_a_price": stock_a.get_price(), "stock_b_price": stock_b.get_price(),
                "stock_a_deals": stock_a_deals, "stock_b_deals": stock_b_deals, "cash": self.cash
            }
        
        if prompt_template is None:
            log.logger.error("Error: prompt_template not set in plan_stock.")
            return {"action_type": "no"}

        try_times = 0
        MAX_TRY_TIMES = 3
        resp = self.run_api(format_prompt(prompt_template, inputs))
        if resp == "": return {"action_type": "no"}

        action_format_check, fail_response, action = self.secretary.check_action(
            resp, self.cash, self.stock_a_amount, self.stock_b_amount,
            stock_a.get_price(), stock_b.get_price()
        )
        while not action_format_check:
            try_times += 1
            if try_times > MAX_TRY_TIMES:
                log.logger.warning(f"Agent {self.order}: Action format try times > MAX_TRY_TIMES. Skip action.")
                action = {"action_type": "no"}; break
            resp = self.run_api(format_prompt(BUY_STOCK_RETRY_PROMPT, {"fail_response": fail_response}))
            if resp == "": action = {"action_type": "no"}; break
            action_format_check, fail_response, action = self.secretary.check_action(
                resp, self.cash, self.stock_a_amount, self.stock_b_amount,
                stock_a.get_price(), stock_b.get_price()
            )

        if action.get("action_type") in ("buy", "sell"):
            log.logger.info(f"INFO: Agent {self.order} decide to action: {action}")
            return action
        else:
            log.logger.info(f"INFO: Agent {self.order} decide not to action")
            return {"action_type": "no"}

    def buy_stock(self, stock_name, price, amount): # Price is passed, amount is passed
        if self.quit: return False
        if self.cash < price * amount or stock_name not in ['A', 'B']:
            log.logger.warning(f"Agent {self.order}: ILLEGAL STOCK BUY BEHAVIOR: cash {self.cash}, trying to buy {amount} of {stock_name} at {price}. Required: {price*amount}")
            return False
        self.cash -= price * amount
        if stock_name == 'A': self.stock_a_amount += amount
        else: self.stock_b_amount += amount
        log.logger.info(f"Agent {self.order} BOUGHT {amount} of {stock_name} at {price}. New cash: {self.cash}")
        return True

    def sell_stock(self, stock_name, price, amount): # Price is passed, amount is passed
        if self.quit: return False
        current_holding = self.stock_b_amount if stock_name == 'B' else self.stock_a_amount
        if current_holding < amount:
            log.logger.warning(f"Agent {self.order}: ILLEGAL STOCK SELL BEHAVIOR: has {current_holding} of {stock_name}, trying to sell {amount}")
            return False
        
        if stock_name == 'A': self.stock_a_amount -= amount
        else: self.stock_b_amount -= amount
        self.cash += price * amount
        log.logger.info(f"Agent {self.order} SOLD {amount} of {stock_name} at {price}. New cash: {self.cash}")
        return True

    def loan_repayment(self, date):
        if self.quit: return
        for loan in list(self.loans):
            if loan.get("repayment_date") == date:
                loan_type_idx = loan.get("loan_type") # This is an index 0, 1, 2
                # Use self.current_loan_rates (which reflects events)
                if loan_type_idx is not None and 0 <= loan_type_idx < len(self.current_loan_rates):
                    repayment_amount = loan["amount"] * (1 + self.current_loan_rates[loan_type_idx])
                    self.cash -= repayment_amount
                    if loan in self.loans: self.loans.remove(loan)
                    log.logger.info(f"Agent {self.order}: Repaid loan {loan['amount']} with interest. New cash: {self.cash}. Loan details: {loan}")
                else:
                    log.logger.error(f"Agent {self.order}: Invalid loan_type index {loan_type_idx} during repayment for loan: {loan}")
        
        if self.cash < 0 and not self.is_bankrupt: # check bankruptcy only if not already flagged
            log.logger.warning(f"Agent {self.order}: Cash became negative ({self.cash}) after loan repayment. Triggering bankruptcy check.")
            self.is_bankrupt = True

    def interest_payment(self):
        if self.quit: return
        for loan in self.loans:
            loan_type_idx = loan.get("loan_type")
            # Use self.current_loan_rates
            if loan_type_idx is not None and 0 <= loan_type_idx < len(self.current_loan_rates):
                # Assuming interest is paid monthly and LOAN_RATE is annual.
                # The original code divides by 12. This should be based on loan duration if it's not monthly payment.
                # For simplicity, sticking to original logic: (annual rate / 12)
                # If REPAYMENT_DAYS are actual payment days (not just interest check days), then interest logic might need adjustment.
                # Based on REPAYMENT_DAYS being [22, 44, ...], these look like monthly equivalent ticks (22 days ~ 1 month)
                interest_due = loan["amount"] * self.current_loan_rates[loan_type_idx] / (self.config['LOAN_TYPE_DATE'][loan_type_idx] / 22.0) # Pro-rata for the period
                # A simpler interpretation: LOAN_RATE is per period defined by LOAN_TYPE_DATE.
                # If Repayment_Days are monthly interest payment days for all loans:
                # interest_due = loan["amount"] * (self.current_loan_rates[loan_type_idx] / (self.config['LOAN_TYPE_DATE'][loan_type_idx]/22) ) # Monthly portion of period rate
                # The original code `util.LOAN_RATE[loan_type] / 12` suggests rates are annual and payments monthly.
                # Let's assume LOAN_RATE from config is "per period" as defined by LOAN_TYPE_DATE
                # And REPAYMENT_DAYS are when *some* interest might be due.
                # For simplicity, if REPAYMENT_DAYS are monthly ticks, then this is monthly interest on all active loans.
                # This part is tricky. Assuming self.current_loan_rates are *period rates* matching LOAN_TYPE_DATE.
                # If REPAYMENT_DAYS are monthly, then we need to calculate monthly equivalent interest.
                # Let's follow the original code's structure of dividing by 12, implying rates are annual.
                # We need to ensure self.current_loan_rates is consistent (annual if dividing by 12).
                # The prompt for plan_loan implies loan_rate1,2,3 are for the loan types. Let's assume these are period rates.
                # So, if REPAYMENT_DAYS are monthly ticks, then no simple division by 12.
                # This needs clarification. For now, let's assume LOAN_RATE in config is *annual* for consistency with original /12.
                annual_rate = self.current_loan_rates[loan_type_idx] # Assuming this is now annual rate
                interest_due = loan["amount"] * annual_rate / 12 
                self.cash -= interest_due
                log.logger.info(f"Agent {self.order}: Paid monthly interest {interest_due} for loan {loan['amount']}. New cash: {self.cash}")
            else:
                log.logger.error(f"Agent {self.order}: Invalid loan_type {loan_type_idx} during interest payment for loan: {loan}")

            if self.cash < 0 and not self.is_bankrupt:
                log.logger.warning(f"Agent {self.order}: Cash became negative ({self.cash}) after interest payment. Triggering bankruptcy check.")
                self.is_bankrupt = True


    def bankrupt_process(self, stock_a_price, stock_b_price):
        # This method seems largely self-contained using agent's current state and passed prices.
        # No direct config access needed here unless bankruptcy rules change based on config.
        if self.quit: return False
        if not self.is_bankrupt and self.cash >=0 : return False 

        log.logger.info(f"Agent {self.order}: Starting bankruptcy process. Cash: {self.cash}, A: {self.stock_a_amount}, B: {self.stock_b_amount}")
        total_value_of_stock = (self.stock_a_amount * stock_a_price + self.stock_b_amount * stock_b_price)

        if total_value_of_stock + self.cash < 0:
            log.logger.warning(f"Agent {self.order} is definitively bankrupt. Total assets {total_value_of_stock + self.cash} are less than 0.")
            self.cash += self.stock_a_amount * stock_a_price; self.stock_a_amount = 0
            self.cash += self.stock_b_amount * stock_b_price; self.stock_b_amount = 0
            self.quit = True; self.is_bankrupt = True
            return True

        if self.cash < 0:
            needed_to_cover_cash = -self.cash
            if self.stock_a_amount > 0 and stock_a_price > 0:
                if stock_a_price * self.stock_a_amount >= needed_to_cover_cash:
                    sell_a_units = math.ceil(needed_to_cover_cash / stock_a_price)
                    self.stock_a_amount -= sell_a_units; self.cash += sell_a_units * stock_a_price
                    log.logger.info(f"Agent {self.order}: Sold {sell_a_units} of Stock A. New cash: {self.cash}")
                    needed_to_cover_cash = 0
                else:
                    self.cash += stock_a_price * self.stock_a_amount
                    needed_to_cover_cash -= stock_a_price * self.stock_a_amount
                    log.logger.info(f"Agent {self.order}: Sold all {self.stock_a_amount} of Stock A. Cash: {self.cash}. Still need: {needed_to_cover_cash}")
                    self.stock_a_amount = 0
            
            if needed_to_cover_cash > 0 and self.stock_b_amount > 0 and stock_b_price > 0:
                if stock_b_price * self.stock_b_amount >= needed_to_cover_cash:
                    sell_b_units = math.ceil(needed_to_cover_cash / stock_b_price)
                    self.stock_b_amount -= sell_b_units; self.cash += sell_b_units * stock_b_price
                    log.logger.info(f"Agent {self.order}: Sold {sell_b_units} of Stock B. New cash: {self.cash}")
                else:
                    self.cash += stock_b_price * self.stock_b_amount
                    log.logger.info(f"Agent {self.order}: Sold all {self.stock_b_amount} of Stock B. Cash: {self.cash}.")
                    self.stock_b_amount = 0

        if self.cash < 0:
            log.logger.error(f"CRITICAL: Agent {self.order} still has negative cash ({self.cash}) after selling stocks.")
            self.quit = True; self.is_bankrupt = True
            return True

        self.is_bankrupt = False
        log.logger.info(f"Agent {self.order}: Bankruptcy process resolved. Cash: {self.cash}, A: {self.stock_a_amount}, B: {self.stock_b_amount}")
        return False

    def post_message(self):
        if self.quit: return ""
        prompt = format_prompt(POST_MESSAGE_PROMPT, inputs={}) # Assuming POST_MESSAGE_PROMPT doesn't need dynamic inputs from config
        return self.run_api(prompt)

    def next_day_estimate(self):
        if self.quit: return {"buy_A": "no", "buy_B": "no", "sell_A": "no", "sell_B": "no", "loan": "no"}
        prompt = format_prompt(NEXT_DAY_ESTIMATE_PROMPT, inputs={}) # Assuming this prompt doesn't need dynamic inputs from config
        resp = self.run_api(prompt)
        if resp == "": return {"buy_A": "no", "buy_B": "no", "sell_A": "no", "sell_B": "no", "loan": "no"}
        
        format_check, fail_response, estimate = self.secretary.check_estimate(resp)
        try_times = 0; MAX_TRY_TIMES = 3
        while not format_check:
            try_times += 1
            if try_times > MAX_TRY_TIMES:
                log.logger.warning(f"Agent {self.order}: Estimation format try times > MAX_TRY_TIMES.")
                estimate = {"buy_A": "no", "buy_B": "no", "sell_A": "no", "sell_B": "no", "loan": "no"}; break
            resp = self.run_api(format_prompt(NEXT_DAY_ESTIMATE_RETRY, {"fail_response": fail_response})) # NEXT_DAY_ESTIMATE_RETRY from agent_prompt.py
            if resp == "": estimate = {"buy_A": "no", "buy_B": "no", "sell_A": "no", "sell_B": "no", "loan": "no"}; break
            format_check, fail_response, estimate = self.secretary.check_estimate(resp)
        return estimate


