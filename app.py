from dotenv import load_dotenv
import os
from save_db import lambda_save_db
from services.openai_services import (
    create_thread,
    create_openai_assistant,
    get_openai_assistant,
    create_openai_client,
)
from reminder_tool import get_reminder_tool
import json


def add_tool_to_assistant(client, assistant_id):
    assistant = get_openai_assistant(client, assistant_id)

    # Verificando se a ferramenta já existe
    tool_names = [tool.function.name for tool in assistant.tools]

    # Se a ferramenta reminder_builder não estiver no assistente, adiciona ela
    if "reminder_builder" not in tool_names:
        reminder_tool = get_reminder_tool()
        updated_tools = assistant.tools + [reminder_tool]

        # Atualizar o assistente com a nova ferramenta
        client.beta.assistants.update(
            assistant_id=assistant_id,
            tools=updated_tools,
        )
        print("Tool 'reminder_builder' adicionada com sucesso.")
    else:
        print("Tool 'reminder_builder' já existe no assistente.")


def send_message_to_assistant(client, assistant_id, thread, reminder_message):

    run = client.beta.threads.runs.create_and_poll(
        thread_id=thread.id,
        assistant_id=assistant_id,
        instructions=reminder_message,
    )

    if run.status == "completed":
        messages = client.beta.threads.messages.list(thread_id=thread.id)
        print(messages)
    elif run.status == "requires_action":
        # Loop through each tool in the required action section
        for tool in run.required_action.submit_tool_outputs.tool_calls:
            if tool.function.name == "reminder_builder":
                # print(tool.function.arguments)
                return tool.function.arguments
    else:
        print(run.status)


def process_reminder(api_response, phone_number):
    # Processa o campo 'gap' para converter em um inteiro
    if "gap" in api_response:

        try:
            # Remove a palavra "hours" ou "hour" e converte para inteiro
            gap_value = (
                api_response["gap"].replace("hours", "").replace("hour", "").strip()
            )
            api_response["gap"] = int(gap_value)
        except ValueError:
            raise ValueError(
                f"Formato inválido para gap: {api_response['gap']}. Esperado: 'X hours'."
            )

    # Adiciona o campo 'phone_number'
    api_response["phone_number"] = phone_number

    # Retorna o JSON formatado de acordo com a necessidade
    return api_response


# Add args in production
def agent():
    load_dotenv()

    ASSISTANT_ID = os.environ.get("ASSISTANT_ID")
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

    client = create_openai_client(key=OPENAI_API_KEY)

    if not ASSISTANT_ID:
        assistant = create_openai_assistant(client=client)
        ASSISTANT_ID = assistant.id
        os.environ["ASSISTANT_ID"] = ASSISTANT_ID
    else:
        assistant = get_openai_assistant(client, ASSISTANT_ID)

    # Check if assistant has the tools
    add_tool_to_assistant(client, ASSISTANT_ID)

    # Change in production
    thread = create_thread(
        client=client, id="1", phone_number="+559842358562", user_name="Teste Teste"
    )

    # Change in production // sometimes duration doesnt come, need to check
    reminder_message = "Remind me to take a break every 2 hours for the next 8 hours."
    api_response = send_message_to_assistant(
        client, ASSISTANT_ID, thread, reminder_message
    )

    obj = json.loads(api_response)
    formated_response = process_reminder(obj, phone_number="+559842358562")

    result = lambda_save_db(formated_response)
    print(result)
    # print(formated_response)

    return api_response


if __name__ == "__main__":
    agent()
