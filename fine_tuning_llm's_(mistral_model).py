!pip install mistralai pandas pyarrow rich gradio

import os

# Set MISTRAL_API_KEY
os.environ['MISTRAL_API_KEY'] = 'Your mistral api key'

# Set WANDB_API_KEY
os.environ['WANDB_API_KEY'] = 'your wandb api key'

"""# Data Preparation"""

import pandas as pd
from rich import print

# Load data from HuggingFace dataset
df = pd.read_parquet('https://huggingface.co/datasets/smangrul/ultrachat-10k-chatml/resolve/main/data/test-00000-of-00001.parquet')

# Split data into train and eval sets
df_train = df.sample(frac=0.995, random_state=200)
df_eval = df.drop(df_train.index)

# Convert to JSON lines format
df_train.to_json("ultrachat_chunk_train.jsonl", orient="records", lines=True)
df_eval.to_json("ultrachat_chunk_eval.jsonl", orient="records", lines=True)

print(df_train.iloc[100]['messages'])

"""# Fine-tuning Setup"""

!python ultrachat_chunk_eval.jsonl
!python ultrachat_chunk_train.jsonl

"""# Fine-tuning the Model"""

import os
import json
import time
from rich import print
from mistralai.client import MistralClient
from mistralai.models.jobs import TrainingParameters
from mistralai.models.chat_completion import ChatMessage
from mistralai.models.jobs import WandbIntegrationIn

# Initialize Mistral client
api_key = os.environ.get("MISTRAL_API_KEY")
client = MistralClient(api_key=api_key)

# Upload training and evaluation datasets
def pprint(obj):
    print(json.dumps(obj.dict(), indent=4))


# 1. Upload the dataset
with open("ultrachat_chunk_train.jsonl", "rb") as f:
    ultrachat_chunk_train = client.files.create(file=("ultrachat_chunk_train.jsonl", f))
with open("ultrachat_chunk_eval.jsonl", "rb") as f:
    ultrachat_chunk_eval = client.files.create(file=("ultrachat_chunk_eval.jsonl", f))

print("Data:")
pprint(ultrachat_chunk_train)
pprint(ultrachat_chunk_eval)


# 2. Create Fine Tuning Job
created_jobs = client.jobs.create(
    model="open-mistral-7b",
    training_files=[ultrachat_chunk_train.id],
    validation_files=[ultrachat_chunk_eval.id],
    hyperparameters=TrainingParameters(
        training_steps=10,
        learning_rate=0.0001,
    ),
    integrations=[
        WandbIntegrationIn(
            project="test_ft_api",
            run_name="test",
            api_key=os.environ.get("WANDB_API_KEY"),
        ).dict()
    ],
)
print("\nCreated Jobs:")
pprint(created_jobs)

"""# Monitor Job Status"""

# 3. Check the Status of the Job
print("\nChecking Job Status:")
retrieved_job = client.jobs.retrieve(created_jobs.id)
while retrieved_job.status in ["RUNNING", "QUEUED"]:
    retrieved_job = client.jobs.retrieve(created_jobs.id)
    pprint(retrieved_job)
    print(f"Job is {retrieved_job.status}, waiting 10 seconds")
    time.sleep(10)

# List all jobs
jobs = client.jobs.list()
pprint(jobs)

# Retrieve specific job details
retrieved_jobs = client.jobs.retrieve(created_jobs.id)
pprint(retrieved_jobs)

"""# Chatbot Deployment"""

# 4. Use the Fine-tuned Model for Chatbot
chat_response = client.chat(
    model=retrieved_jobs.fine_tuned_model,
    messages=[ChatMessage(role='user', content='What is the best French cheese?')]
)
print("\nTesting Fine-tuned Model:")
pprint(chat_response)

import os
import json
import time
from rich import print
from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage

client = MistralClient(api_key=os.environ.get("MISTRAL_API_KEY"))

chat_response = client.chat(
    model="ft:open-mistral-7b:c6c6e431:20240625:fd193453",
    messages=[ChatMessage(role='user', content='What is the best French cheese?')]
)
print(chat_response)

"""# Gradio Interface"""

import os
from rich import print
from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage
import gradio as gr

# Function to get chat response
def get_chat_response(user_input):
    client = MistralClient(api_key=os.environ.get("MISTRAL_API_KEY"))
    chat_response = client.chat(
        model="ft:open-mistral-7b:c6c6e431:20240625:fd193453",
        messages=[ChatMessage(role='user', content=user_input)]
    )
    content = chat_response.choices[0].message.content
    return content

# Gradio Interface
iface = gr.Interface(
    fn=get_chat_response,
    inputs="text",
    outputs="text",
    title="Mistral AI Chatbot",
    description="Ask the chatbot any question.",
)

iface.launch()
