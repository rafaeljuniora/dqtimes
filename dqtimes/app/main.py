import os
import io
import asyncio
import json
import dask.dataframe as dd
import tempfile
from dask.distributed import Client, LocalCluster
from app import forecast_temp
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query
from app.tasks import task_dummy, projection_task, task_long_running
from app.celery_app import celery_app
import math
import time
from typing import Dict, Any

# Iniciar um cluster local e um cliente Dask
cluster = LocalCluster()
client = Client(cluster)

app = FastAPI()


@app.on_event("startup")
async def startup_event():
    print(f"Dask Dashboard is available at {client.dashboard_link}")


@app.post("/projecao_lista/")
async def upload_file(
    lista_historico: str = Form(...),
    quantidade_projecoes: int = Form(...),
):

    lista_original = json.loads(lista_historico)  # Convertendo para lista

    n = quantidade_projecoes 

    # Chamando a função de previsão
    resultado = forecast_temp(lista_original, n)

    return {
        "projecoes": resultado
    }

@app.post("/projecao_dataframe/")
async def upload_file(
    csv_dataframe: UploadFile = File(...),
    quantidade_projecoes: int = Form(...),
    header: bool = Form(...),
    index_col: bool = Form(...),
    page: int = Query(1, ge=1),  # Número da página, deve ser >= 1
    page_size: int = Query(10, ge=1),  # Tamanho da página, deve ser >= 1
):
    n = quantidade_projecoes

    # Salvar o conteúdo do arquivo em um arquivo temporário
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp_file:
        tmp_file.write(await csv_dataframe.read())
        tmp_file_path = tmp_file.name

    ddf = dd.read_csv(tmp_file_path, header=0 if header else None)

    if index_col:
        ddf = ddf.drop(ddf.columns[0], axis=1)

    # Calcular o número total de linhas e o número total de páginas
    total_rows = len(ddf)
    total_pages = math.ceil(total_rows / page_size)

    # Verificar se o número da página é válido
    if page > total_pages:
        raise HTTPException(status_code=404, detail="Page number out of range")

    # Calcular o índice inicial e final para a paginação
    start_index = (page - 1) * page_size
    end_index = start_index + page_size

    # Aplicar a paginação ao DataFrame
    ddf_paginated = ddf.loc[start_index:end_index]

    start_time = time.time()
    lista_df = []

    for part in ddf_paginated.to_delayed():
        # Converter a partição para um pandas DataFrame e iterar sobre as linhas
        for index, row in part.compute().iterrows():
            lista_df.append(row.tolist())

    # Aplica a função de projeção à lista de listas
    
    resultado = []
    for lista in lista_df:
        projection = forecast_temp(lista, n)
        resultado.append(projection)

    end_time = time.time()
    execution_time = end_time - start_time 

    return {
        "execution_time": execution_time,
        "total_pages": total_pages,
        "current_page": page,
        "projecoes": resultado
    }


# ========== ENDPOINTS CELERY ==========

@app.post("/task/dummy")
async def create_dummy_task(data: Dict[str, Any] = None):
    """
    Endpoint para executar a task dummy assíncronamente.
    Implementa o round-trip: request API → enfileira → executa → retorna ID.
    """
    if data is None:
        data = {"test": "dummy data"}
    
    # Enfileira a task
    task = task_dummy.delay(data)
    
    return {
        "task_id": task.id,
        "status": "pending",
        "message": "Task dummy enfileirada com sucesso"
    }


@app.post("/task/projection")
async def create_projection_task_async(
    lista_historico: str = Form(...),
    quantidade_projecoes: int = Form(...),
):
    """
    Endpoint assíncrono para realizar projeções de dados.
    Retorna o ID da task para acompanhamento posterior.
    """
    lista_original = json.loads(lista_historico)
    
    # Enfileira a task assíncrona
    task = projection_task.delay(lista_original, quantidade_projecoes)
    
    return {
        "task_id": task.id,
        "status": "pending",
        "message": "Task de projeção enfileirada com sucesso",
        "quantidade_projecoes": quantidade_projecoes
    }


@app.post("/task/long-running")
async def create_long_running_task(iterations: int = Form(10)):
    """
    Endpoint para testar operações longas de forma assíncrona.
    """
    task = task_long_running.delay(iterations)
    
    return {
        "task_id": task.id,
        "status": "pending",
        "iterations": iterations,
        "message": "Task long-running enfileirada com sucesso"
    }


@app.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """
    Retorna o status da task (pending, in execution, completed, failed).
    Permite acompanhar o progresso da execução.
    """
    task = celery_app.AsyncResult(task_id)
    
    if task.state == "PENDING":
        response = {
            "task_id": task_id,
            "status": "pending",
            "message": "Task está aguardando execução"
        }
    elif task.state == "PROGRESS":
        response = {
            "task_id": task_id,
            "status": "in execution",
            "progress": task.info,
            "message": "Task está sendo executada"
        }
    elif task.state == "SUCCESS":
        response = {
            "task_id": task_id,
            "status": "completed",
            "result": task.result,
            "message": "Task concluída com sucesso"
        }
    elif task.state == "FAILURE":
        response = {
            "task_id": task_id,
            "status": "failed",
            "error": str(task.info),
            "message": "Task falhou na execução"
        }
    else:
        response = {
            "task_id": task_id,
            "status": task.state,
            "message": "Status desconhecido"
        }
    
    return response


@app.get("/health")
async def health_check():
    """
    Verifica a saúde da API e do Celery.
    """
    try:
        # Verifica se o Celery está respondendo
        celery_stats = celery_app.control.inspect().stats()
        
        return {
            "api": "healthy",
            "celery": "connected" if celery_stats else "disconnected",
            "timestamp": time.time()
        }
    except Exception as e:
        return {
            "api": "healthy",
            "celery": f"error: {str(e)}",
            "timestamp": time.time()
        }
