"""LangGraph workflow that analyzes 10-Q Item 2 data."""

from edgar import Company, set_identity
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from dotenv import load_dotenv
import os
import re
import getpass as getpass
from typing import Annotated
from typing_extensions import TypedDict
from toolsmod import cache_fetcher, edgar_fetcher
import json


def model_init():
    """Initialize analysis and judge models, prompting for keys if needed."""

    load_dotenv()

    def _set_env(key: str):
        if not os.environ.get(key):  # This checks for None or an empty string
            os.environ[key] = getpass.getpass(f"{key}: ")

    _set_env("OPENAI_API_KEY")
    
    _set_env("GOOGLE_API_KEY")

    class judge(BaseModel):
        """Schema describing the Gemini judge response payload."""

        passorfail: str = Field(
            description=(
                " I want you to print a 'pass' or 'fail' in the 'passorfail' make"
                " sure to not write anything else exept 'pass' or 'fail'"
            )
        )
        anomalies: str = Field(
            description=(
                "and if the report fails write your concutions for the"
                " incorrectness of the report in the anomalies section. "
            )
        )

    model = ChatOpenAI(
        model="gpt-5-mini",
        max_tokens=None,
        timeout=None,
        max_retries=2,
        temperature=0.0,
    ).with_structured_output(method="json_mode")

    judge_model = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0,
        max_tokens=None,
        timeout=None,
        max_retries=2,
    ).with_structured_output(judge, method="json_mode")
    return model, judge_model


class State(TypedDict):
    """Shared state that flows between LangGraph nodes."""

    # Conversation history that LangGraph expects for message-passing graphs.
    messages: Annotated[list, add_messages]

    # [ticker, cik, filing_date] tuple returned from the fetch step.
    stockinfo: list

    # Raw Item 2 content extracted from a 10-Q filing.
    tenqitem2cont: str

    # Structured JSON report outputs for each analyzer.
    revenue_report: str
    revenue_report_exist: str

    cashflow_report: str
    cashflow_report_exist: str

    debt_report: str
    debt_report_exist: str


def tool_node(state: State):
    """Fetch Item 2 content either from cache or directly via EDGAR."""

    # Identify ourselves to the ``edgar`` client before calling remote APIs.
    set_identity("jacob casey jacobrcasey135@gmail.com")

    user_input = input("would you like to use cache mode (y or n): ").lower()
    if user_input == "y":
        try:
            # Attempt to reuse cached filings to reduce EDGAR load/latency.
            tenqitem2cont, stockinfo = cache_fetcher()
            state_update = {"stockinfo": stockinfo, "tenqitem2cont": tenqitem2cont}
            return Command(update=state_update)
        except Exception:
            print("error in cache_fetcher using edgar fetcher")
            try:
                # Cache missed or failed—fallback to live EDGAR retrieval.
                tenqitem2cont, stockinfo = edgar_fetcher()
                state_update = {"stockinfo": stockinfo, "tenqitem2cont": tenqitem2cont}
                return Command(update=state_update)
            except Exception:
                print("error running edgar_fetcher")
                exit

    else:
        print("using fetch mode")
        try:
            tenqitem2cont, stockinfo = edgar_fetcher()
            state_update = {"stockinfo": stockinfo, "tenqitem2cont": tenqitem2cont}
            return Command(update=state_update)
        except Exception:
            print("error in edgar_fetcher")
            exit
    return

def revenue_llm(state: State):
    """Generate the revenue analysis JSON report."""

    stockinfo = state["stockinfo"]
    path_company_date = f"output/{stockinfo[0]}/{stockinfo[2]}"
    file_path = f"{path_company_date}/revenue_{stockinfo[2]}.json"

    # Skip regeneration if a validated report already exists on disk.
    if os.path.exists(file_path):
        print(f"The path '{file_path}' exists.")
        revenue_report_exist = "y"
        state_update = {"revenue_report_exist": revenue_report_exist}
        return Command(update=state_update)
    else:
        print(f"The path '{file_path}' does not exist.")

    tenqitem2cont = state["tenqitem2cont"]
    model, _ = model_init()

    # Prompt captures detailed instructions for how the JSON should be structured.
    msg = [
        HumanMessage(
            content= f"""
    INPUT: you will be given the entire item 2 of a 10-q form 
    
    
    here is the form: "{tenqitem2cont}"

            """ + """


    --ROLE: You are a expert finacial analyst that specilises in reading and understanding 10-q and specificly the revenues

    --JOB: review the content to determine why the company's revenues increase/decrease Did it increase its sales from increased sales and 
    services (organic) or was it from an aquisition, gants or settlements (inorganic)? 


    --OUTPUT INSTRUCTIONS: 
    -I want you to do a revenue analisys of the text provided what did the company do to lose or gain revenue 
    -quote numbers from the provided texts to back up your claims of revenue gain or loss inside the respective json sections. 
    -make sure when you are doing the revenue streams and growth type to list the streams from highest gain to lowest so majority revenue to least majority.
    -quote the quarter time frame for each change in revenue in the drive section after the amount or percentage is stated.
    -if a number is in thousands make sure to state that the number is in thousands
    -the instructions for each section will be listed below. 
    -YOU MUST FOLLOW THE JSON FORMATTING BELOW EXACTLY THE ONLY CHAGES YOU CAN MAKE IS REPEAT THE SECTIONS THAT SAY IN THE DESCRIPTIONS THAT THEY CAN BE REPEATED
    
    --OUTPUT SCHEMA AND OUTPUT INSTRUCTIONS (JSON) = { 
    "company name": "name of the company",
    "headline result": "what is the general report of the revenue losses or gains this is a summary section", 
    "what drove the revenue change": "what are the main drivers of the revenue changes loss or gain",
    "revenue streams and growth type": { 
        "revenue stream": "this is detailed what is the specific revenue stream you are analising you should repeat this for every stream of revenue. MAKE SURE TO INCLUDE EVERY STATED REVENUE STREAM FROM THE 10-Q EXACTLY",
        "driver": "what is the gain or loss of revenue and why did this specific revenue stream gain or lose money you should repeat this for every driver for every stream",
        "organic or inorganic": "was the gain or loss in revenue organic or inorganic (orgainic is repetable growth or loss. and inorganic is one time events that are not likely repetable gain or loss) you should repeat this for every previous driver and stream.",
        },
    }

    """,
        )
    ]

    # Invokes the model for the response
    revenue_report = model.invoke(msg)

    # State update
    state_update = {"revenue_report": revenue_report }
    return Command(update=state_update)

def gemini_judge_revenue(state: State):
    """Validate the revenue report and persist it if it passes."""

    stockinfo = state["stockinfo"]

    try:
        revenue_report_exist = state["revenue_report_exist"]
        if revenue_report_exist == "y":
            print("skipping judge revenue report already exists")
            return
    except Exception:
        print("entering judge")

    tenqitem2cont = state["tenqitem2cont"]
    revenue_report = state["revenue_report"]
    _, judge_model = model_init()

    # judge prompt
    msg = [
        HumanMessage(
            content= f"""
    INPUT: you will be given the entire item 2 of a 10-q form 
    
    
    here is the form: "{tenqitem2cont}"

    here is the first llm's revenue response to this document: "{revenue_report}"

            """ + """


    --ROLE: You are a expert finacial analyst that specilises in judging a llm's output 

    --JOB: review the content to determine if the revenue report is correct for the given section of the 10-q form


    --OUTPUT INSTRUCTIONS: I want you to print a "pass" or "fail" in the "passorfail" make sure to not write anything else exept "pass" or "fail" and if the report fails 
    write your concutions for the incorrectness of the report in the anomalies section. 

    --OUTPUT FORMAT = { 
    "passorfail": "your response here", 
    "anomalies": "your response here",
    }
    """,
        )
    ]

    # model invoke
    revenue_judge_report = judge_model.invoke(msg)

    # debug
    #print(revenue_judge_report)

    # only grabs the pass or fail object
    passorfail = revenue_judge_report.passorfail

    if passorfail == 'pass':

        # define dir structure
        path_company = f"output/{stockinfo[0]}"
        path_company_date = f"output/{stockinfo[0]}/{stockinfo[2]}"
        os.makedirs(path_company, exist_ok=True)
        try:
            os.mkdir(path_company_date)
        except FileExistsError:
            print("file alread exists")
            pass

        # Writes the json to revenue_date.json to the nested dirs
        with open(f"{path_company_date}/revenue_{stockinfo[2]}.json", 'w') as f:
            json.dump(revenue_report, f, indent=4)
    elif passorfail == 'fail':
        # if a fail prints the anomalies for analisis 
        print("this report has failed")
        print("anomalies:", revenue_judge_report.anomalies)

    else:
        # if the model writes something different then "pass" or "fail"
        print("error in passorfail section of judge json check model formatting")

    return
    

def cashflow_llm(state: State):
    """Generate the cashflow analysis JSON report."""

    stockinfo = state["stockinfo"]
    path_company_date = f"output/{stockinfo[0]}/{stockinfo[2]}"
    file_path = f"{path_company_date}/cashflow_{stockinfo[2]}.json"

    if os.path.exists(file_path):
        print(f"The path '{file_path}' exists.")
        cashflow_report_exist = "y"
        state_update = {"cashflow_report_exist": cashflow_report_exist}
        return Command(update=state_update)
    else:
        print(f"The path '{file_path}' does not exist.")

    tenqitem2cont = state["tenqitem2cont"]
    model, _ = model_init()

    # cashflow prompt
    msg = [
        HumanMessage(
            content= f"""
    INPUT: you will be given the entire item 2 of a 10-q form 
    
    
    here is the form: "{tenqitem2cont}"

            """ + """


    --ROLE: You are a expert finacial analyst that specilises in reading and understanding 10-q and specificly the cashflows

    --JOB: review the content to determine why the company's cashflow increase/decrease Did cashflow increased from sales and 
    services (organic) or was it from an aquisition, gants or settlements (inorganic)? 


    --OUTPUT INSTRUCTIONS: 
    -I want you to do a cashflow analisys of the text provided what did the company do to lose or gain operating chashflow.
    -quote numbers from the provided texts to back up your claims of cashflow gain or loss inside the respective json sections.
    -quote the quarter time frame for each change in cashflow in the drive section after the amount or percentage is stated.
    -if a number is in thousands make sure to state that the number is in thousands
    -the instructions for each section will be listed below.
    -DO NOT ADD ANY EXTRA SECTIONS TO THE JSON FORMATTING
    
    --OUTPUT SCHEMA AND OUTPUT INSTRUCTIONS (JSON) = {
    "company name": "name of the company",
    "headline result": "what is the general report of the cashflow losses or gains this is a summary section", 
    "cashflow and growth type": { 
        "operating cashflow": "this is a summary of operating cashflow. is it negitive or positive.",
        "driver": "what is the gain or loss of operating cashflow and why did this metric gain or lose money",
        },
    }

    """,
        )
    ]

    # model invoke
    cashflow_report = model.invoke(msg)

    state_update = {"cashflow_report": cashflow_report }
    return Command(update=state_update)


def gemini_judge_cashflow(state: State):
    """Validate the cashflow report and write it to disk if approved."""

    stockinfo = state["stockinfo"]

    try:
        cashflow_report_exist = state["cashflow_report_exist"]
        if cashflow_report_exist == "y":
            print("skipping judge cashflow report already exists")
            return
    except Exception:
        print("entering judge")

    tenqitem2cont = state["tenqitem2cont"]
    cashflow_report = state["cashflow_report"]
    _, judge_model = model_init()

    

    msg = [
        HumanMessage(
            content= f"""
    INPUT: you will be given the entire item 2 of a 10-q form 
    
    
    here is the form: "{tenqitem2cont}"

    here is the first llm's cashflow response to this document: "{cashflow_report}"

            """ + """


    --ROLE: You are a expert finacial analyst that specilises in judging a llm's output 

    --JOB: review the content to determine if the cashflow report is correct for the given section of the 10-q form


    --OUTPUT INSTRUCTIONS: I want you to print a "pass" or "fail" in the "passorfail" make sure to not write anything else exept "pass" or "fail" and if the report fails 
    write your concutions for the incorrectness of the report in the anomalies section. 

    --OUTPUT FORMAT = { 
    "passorfail": "your response here", 
    "anomalies": "your response here",
    }
    """,
        )
    ]

    cashflow_judge_report = judge_model.invoke(msg)

    print(cashflow_judge_report)

    passorfail = cashflow_judge_report.passorfail

    if passorfail == 'pass':
        print("report has passed judging")
        print("caching and displaying report")

        path_company = f"output/{stockinfo[0]}"
        path_company_date = f"output/{stockinfo[0]}/{stockinfo[2]}"
        os.makedirs(path_company, exist_ok=True)
        try:
            os.mkdir(path_company_date)
        except FileExistsError:
            print("file alread exists")
            pass

        print(f"Nested directories '{path_company_date}' created (or already exist).")
        with open(f"{path_company_date}/cashflow_{stockinfo[2]}.json", 'w') as f:
            json.dump(cashflow_report, f, indent=4)
    elif passorfail == 'fail':
        print("this report has failed")
        print("anomalies:", cashflow_judge_report.anomalies)

    else:
        print("error in passorfail section of judge json check model formatting")

    return

def debt_llm(state: State):
    """Generate the debt analysis JSON report."""

    print("entered debt LLM")

    stockinfo = state["stockinfo"]
    path_company_date = f"output/{stockinfo[0]}/{stockinfo[2]}"
    file_path = f"{path_company_date}/debt_{stockinfo[2]}.json"

    if os.path.exists(file_path):
        print(f"The path '{file_path}' exists.")
        debt_report_exist = "y"
        state_update = {"debt_report_exist": debt_report_exist}
        return Command(update=state_update)
    else:
        print(f"The path '{file_path}' does not exist.")

    tenqitem2cont = state["tenqitem2cont"]
    model, _ = model_init()

    msg = [
        HumanMessage(
            content= f"""
    INPUT: you will be given the entire item 2 of a 10-q form 
    
    
    here is the form: "{tenqitem2cont}"

            """ + """


    --ROLE: You are a expert finacial analyst that specilises in reading and understanding 10-q and specificly the debt

    --JOB: review the content to determine why the company's debt increase/decrease Did it increase its debt, was the debt good or bad debt


    --OUTPUT INSTRUCTIONS: 
    -I want you to do a debt analisys of the text provided what did the company do to lose or gain debt 
    -quote numbers from the provided texts to back up your claims of debt gain or loss inside the respective json sections. 
    -make sure when you are doing the debt sections list highest source of debt to lowest source of debt
    -quote the quarter time frame for each change in debt in the drive section after the amount or percentage is stated.
    -if a number is in thousands make sure to state that the number is in thousands
    -the instructions for each section will be listed below. 
    -DO NOT ADD ANY EXTRA SECTIONS TO THE JSON FORMATTING.
    
    --OUTPUT SCHEMA AND OUTPUT INSTRUCTIONS (JSON) = { 
    "company name": "name of the company",
    "what_changed_with_debt": "<e.g., 'Debt fell by ~$200M due to repayment' or 'Debt rose ~$500M from new notes'>",
    "why_it_changed": "<brief reason — refinancing, working capital, acquisition, etc.>",
    "can_they_pay_bills": "<near-term cash sources/uses; include revolver availability>",
    "management_plan": "<how they plan to fund needs — operations, revolver, refinance, asset sales, equity>",
    }

    """,
        )
    ]

    
    debt_report = model.invoke(msg)
    
    state_update = {"debt_report": debt_report }

    return Command(update=state_update)

def gemini_judge_debt(state: State):
    """Validate the debt report before it is cached."""

    stockinfo = state["stockinfo"]

    try:
        debt_report_exist = state["debt_report_exist"]
        if debt_report_exist == "y":
            print("skipping judge debt report already exists")
            return
    except Exception:
        print("entering judge")

    tenqitem2cont = state["tenqitem2cont"]
    debt_report = state["debt_report"]

    _, judge_model = model_init()

    msg = [
        HumanMessage(
            content= f"""
    INPUT: you will be given the entire item 2 of a 10-q form 
    
    
    here is the form: "{tenqitem2cont}"

    here is the first llm's debt report to this document: "{debt_report}"

            """ + """


    --ROLE: You are a expert finacial analyst that specilises in judging a llm's output 

    --JOB: review the content to determine if the debt report is correct for the given section of the 10-q form


    --OUTPUT INSTRUCTIONS: I want you to print a "pass" or "fail" in the "passorfail" make sure to not write anything else exept "pass" or "fail" and if the report fails 
    write your concutions for the incorrectness of the report in the anomalies section. 

    --OUTPUT FORMAT = { 
    "passorfail": "your response here", 
    "anomalies": "your response here",
    }
    """,
        )
    ]

    debt_judge_report = judge_model.invoke(msg)

    passorfail = debt_judge_report.passorfail

    if passorfail == 'pass':
        print("report has passed judging")
        print("caching and displaying report")
        
        path_company = f"output/{stockinfo[0]}"
        path_company_date = f"output/{stockinfo[0]}/{stockinfo[2]}"
        os.makedirs(path_company, exist_ok=True)
        try:
            os.mkdir(path_company_date)
        except FileExistsError:
            print("file alread exists")
            pass
        print(f"Nested directories '{path_company_date}' created (or already exist).")
        with open(f"{path_company_date}/debt_{stockinfo[2]}.json", 'w') as f:
            json.dump(debt_report, f, indent=4)
    elif passorfail == 'fail':
        print("this report has failed")
        print("anomalies:", debt_judge_report.anomalies)

    else:
        print("error in passorfail section of judge json check model formatting")

    return


def main():
    """Build and run the sequential LangGraph pipeline indefinitely."""

    graph_builder = StateGraph(State)

    # Register every node that participates in the workflow.
    graph_builder.add_node("revenue_llm", revenue_llm)
    graph_builder.add_node("tool", tool_node)
    graph_builder.add_node("gemini_judge_revenue", gemini_judge_revenue)
    graph_builder.add_node("cashflow_llm", cashflow_llm)
    graph_builder.add_node("gemini_judge_cashflow", gemini_judge_cashflow)
    graph_builder.add_node("debt_llm", debt_llm)
    graph_builder.add_node("gemini_judge_debt", gemini_judge_debt)

    graph_builder.set_entry_point("tool")

    # Simple linear path from data acquisition through every report + judge.
    graph_builder.add_edge("tool", "revenue_llm")
    graph_builder.add_edge("revenue_llm", "gemini_judge_revenue")
    graph_builder.add_edge("gemini_judge_revenue", "cashflow_llm")
    graph_builder.add_edge("cashflow_llm", "gemini_judge_cashflow")
    graph_builder.add_edge("gemini_judge_cashflow", "debt_llm")
    graph_builder.add_edge("debt_llm", "gemini_judge_debt")
    graph_builder.add_edge("gemini_judge_debt", END)

    graph = graph_builder.compile()

    while True:
        graph.invoke({"messages": ["Init graph"]})


if __name__ == "__main__":
    result = main()