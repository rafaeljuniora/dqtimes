import os
import io
import asyncio
import json
import dask.dataframe as dd
import tempfile
from dask.distributed import Client, LocalCluster
from aplicacao import forecast_temp
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query, status
import math
import time
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator, conint
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
from celery import Celery
import logging

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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

celery_app = Celery(
    'forecast_tasks',
    broker='redis://localhost:6379/0',  #RabbitMQ(sei la oque deu naquela discussão): 'amqp://localhost:5672//'
    backend='redis://localhost:6379/0'
)

cluster = LocalCluster()
client = Client(cluster)

app = FastAPI()


class ProjecaoListaRequest(BaseModel):
    lista_historico: str = Field(..., description="Lista histórica em formato JSON string")
    quantidade_projecoes: conint(gt=0) = Field(..., description="Número de projeções a serem feitas")

    @validator('lista_historico')
    def validate_lista_historico(cls, v):
        try:
            lista = json.loads(v)
            if not isinstance(lista, list):
                raise ValueError("Deve ser uma lista")
            if len(lista) == 0:
                raise ValueError("Lista não pode estar vazia")
            if not all(isinstance(item, (int, float)) for item in lista):
                raise ValueError("Todos os elementos devem ser números")
            return v
        except json.JSONDecodeError:
            raise ValueError("Formato JSON inválido")

class ProjecaoDataframeRequest(BaseModel):
    quantidade_projecoes: conint(gt=0) = Field(..., description="Número de projeções a serem feitas")
    header: bool = Field(..., description="Se o CSV possui header")
    index_col: bool = Field(..., description="Se o CSV possui coluna de índice")
    page: conint(ge=1) = Field(1, description="Número da página")
    page_size: conint(ge=1) = Field(10, description="Tamanho da página")

class ProjecaoResponse(BaseModel):
    projecoes: List[float]
    task_id: Optional[str] = None
    status: str = "completed"
    execution_time: Optional[float] = None
    total_pages: Optional[int] = None
    current_page: Optional[int] = None

class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str
    created_at: datetime

@celery_app.task(bind=True)
def process_forecast_lista(self, lista_historico: str, quantidade_projecoes: int, user_metadata: Dict[str, Any]):
    """Task Celery para processamento assíncrono de lista"""
    try:
        lista_original = json.loads(lista_historico)
        resultado = forecast_temp(lista_original, quantidade_projecoes)
        
        return {
            "projecoes": resultado,
            "user_metadata": user_metadata,
            "status": "completed"
        }
    except Exception as e:
        self.update_state(state='FAILURE', meta={'exc': str(e)})
        raise

@celery_app.task(bind=True)
def process_forecast_dataframe(self, file_path: str, quantidade_projecoes: int, 
                              header: bool, index_col: bool, page: int, page_size: int,
                              user_metadata: Dict[str, Any]):
    """Task Celery para processamento assíncrono de dataframe"""
    try:
        ddf = dd.read_csv(file_path, header=0 if header else None)

        if index_col:
            ddf = ddf.drop(ddf.columns[0], axis=1)

        total_rows = len(ddf)
        total_pages = math.ceil(total_rows / page_size)

        if page > total_pages:
            raise ValueError("Page number out of range")

        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        ddf_paginated = ddf.loc[start_index:end_index]

        start_time = time.time()
        lista_df = []

        for part in ddf_paginated.to_delayed():
            for index, row in part.compute().iterrows():
                lista_df.append(row.tolist())

        resultado = []
        for lista in lista_df:
            projection = forecast_temp(lista, quantidade_projecoes)
            resultado.append(projection)

        end_time = time.time()
        execution_time = end_time - start_time

        os.unlink(file_path)

        return {
            "projecoes": resultado,
            "execution_time": execution_time,
            "total_pages": total_pages,
            "current_page": page,
            "user_metadata": user_metadata,
            "status": "completed"
        }
    except Exception as e:
        if os.path.exists(file_path):
            os.unlink(file_path)
        self.update_state(state='FAILURE', meta={'exc': str(e)})
        raise


@app.on_event("startup")
async def startup_event():
    print(f"Dask Dashboard is available at {client.dashboard_link}")

@app.post("/projecao_lista/", response_model=ProjecaoResponse)
async def upload_file_lista(
    lista_historico: str = Form(...),
    quantidade_projecoes: int = Form(...),
    async_processing: bool = Form(False)
):
    """
    Endpoint para projeção a partir de lista
    
    - Valida dados de entrada
    - Suporte a processamento síncrono e assíncrono
    - Retorna respostas padronizadas
    """
    try:
        request_data = ProjecaoListaRequest(
            lista_historico=lista_historico,
            quantidade_projecoes=quantidade_projecoes
        )
        
        if async_processing:
            task_id = str(uuid.uuid4())
            user_metadata = {
                "endpoint": "projecao_lista",
                "timestamp": datetime.now().isoformat(),
                "quantidade_projecoes": quantidade_projecoes
            }
            
            process_forecast_lista.apply_async(
                args=[lista_historico, quantidade_projecoes, user_metadata],
                task_id=task_id
            )
            
            return JSONResponse(
                status_code=status.HTTP_202_ACCEPTED,
                content={
                    "task_id": task_id,
                    "status": "processing",
                    "message": "Task enfileirada para processamento assíncrono"
                }
            )
        else:
            lista_original = json.loads(lista_historico)
            resultado = forecast_temp(lista_original, quantidade_projecoes)
            
            return ProjecaoResponse(projecoes=resultado)

    except Exception as e:
        logger.error(f"Erro no processamento da lista: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Erro de validação: {str(e)}"
        )

@app.post("/projecao_dataframe/", response_model=ProjecaoResponse)
async def upload_file_dataframe(
    csv_dataframe: UploadFile = File(...),
    quantidade_projecoes: int = Form(...),
    header: bool = Form(...),
    index_col: bool = Form(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1),
    async_processing: bool = Form(False)
):
    """
    Endpoint para projeção a partir de dataframe CSV
    
    - Valida dados de entrada
    - Suporte a processamento síncrono e assíncrono
    - Paginação de resultados
    """
    try:
        request_data = ProjecaoDataframeRequest(
            quantidade_projecoes=quantidade_projecoes,
            header=header,
            index_col=index_col,
            page=page,
            page_size=page_size
        )

        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp_file:
            content = await csv_dataframe.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name

        if async_processing:
            task_id = str(uuid.uuid4())
            user_metadata = {
                "endpoint": "projecao_dataframe",
                "filename": csv_dataframe.filename,
                "timestamp": datetime.now().isoformat(),
                "quantidade_projecoes": quantidade_projecoes,
                "page": page,
                "page_size": page_size
            }
            
            process_forecast_dataframe.apply_async(
                args=[tmp_file_path, quantidade_projecoes, header, index_col, page, page_size, user_metadata],
                task_id=task_id
            )
            
            return JSONResponse(
                status_code=status.HTTP_202_ACCEPTED,
                content={
                    "task_id": task_id,
                    "status": "processing",
                    "message": "Task enfileirada para processamento assíncrono"
                }
            )
        else:
            ddf = dd.read_csv(tmp_file_path, header=0 if header else None)

            if index_col:
                ddf = ddf.drop(ddf.columns[0], axis=1)

            total_rows = len(ddf)
            total_pages = math.ceil(total_rows / page_size)

            if page > total_pages:
                os.unlink(tmp_file_path)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Page number out of range"
                )

            start_index = (page - 1) * page_size
            end_index = start_index + page_size
            ddf_paginated = ddf.loc[start_index:end_index]

            start_time = time.time()
            lista_df = []

            for part in ddf_paginated.to_delayed():
                for index, row in part.compute().iterrows():
                    lista_df.append(row.tolist())

            resultado = []
            for lista in lista_df:
                projection = forecast_temp(lista, quantidade_projecoes)
                resultado.append(projection)

            end_time = time.time()
            execution_time = end_time - start_time

            os.unlink(tmp_file_path)

            return ProjecaoResponse(
                projecoes=resultado,
                execution_time=execution_time,
                total_pages=total_pages,
                current_page=page
            )

    except Exception as e:
        if 'tmp_file_path' in locals() and os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)
        
        logger.error(f"Erro no processamento do dataframe: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Erro de processamento: {str(e)}"
        )

@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """
    Endpoint para verificar status de uma task
    """
    try:
        task = celery_app.AsyncResult(task_id)
        
        if task.state == 'PENDING':
            return TaskResponse(
                task_id=task_id,
                status="pending",
                message="Task está na fila aguardando processamento",
                created_at=datetime.now()
            )
        elif task.state == 'PROGRESS':
            return TaskResponse(
                task_id=task_id,
                status="processing",
                message="Task está sendo processada",
                created_at=datetime.now()
            )
        elif task.state == 'SUCCESS':
            return TaskResponse(
                task_id=task_id,
                status="completed",
                message="Task processada com sucesso",
                created_at=datetime.now()
            )
        else:
            return TaskResponse(
                task_id=task_id,
                status="failed",
                message=f"Task falhou: {task.info.get('exc', 'Erro desconhecido')}",
                created_at=datetime.now()
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task não encontrada: {str(e)}"
        )

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.now().isoformat()
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Erro interno: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Erro interno do servidor",
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "timestamp": datetime.now().isoformat()
        }
    )