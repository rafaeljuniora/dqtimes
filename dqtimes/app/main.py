import os
import io
import json
import math
import time
import uuid
import logging
import asyncio
import tempfile
from datetime import datetime
from typing import List, Optional, Dict, Any
from copy import copy as cp
import numpy as np

import dask.dataframe as dd
from dask.distributed import Client, LocalCluster
from celery import Celery
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator, conint

def tax_acrescimo(lista: list) -> tuple:
    """Placeholder: Retorna taxas de crescimento/decréscimo dummy."""
    print("AVISO: Usando a função placeholder 'tax_acrescimo'.")
    return (0.05, -0.02)

def binariza(lista: list, arg1: int, arg2: int) -> list:
    """Placeholder: Retorna uma lista binarizada dummy."""
    print("AVISO: Usando a função placeholder 'binariza'.")
    return [1 if x > np.mean(lista) else 0 for x in lista]

def inferencia_bayes_bin_general(lista: list, n_binarizacao: int) -> tuple:
    """Placeholder: Retorna uma probabilidade dummy."""
    print("AVISO: Usando a função placeholder 'inferencia_bayes_bin_general'.")
    return (0.6,) 

def media_suave4(lista: list, n_de_prevs: int) -> list:
    """Placeholder: Faltava no código original, mas era chamada."""
    print("AVISO: Usando a função placeholder 'media_suave4'.")
    return media_movel4(lista, n_de_prevs)

def media_suave12(lista: list, n_de_prevs: int) -> list:
    """Placeholder: Faltava no código original, mas era chamada."""
    print("AVISO: Usando a função placeholder 'media_suave12'.")
    return media_movel12(lista, n_de_prevs)

def naive_bayes(lista, n_de_prevs):
    lista1 = cp(lista)
    prevs = []
    contador = 1
    taxa = tax_acrescimo(lista)
    while contador <= n_de_prevs:
        n_binarizacao = min(max(len(lista1) - 1, 2), 6)
        a = binariza(lista1, n_binarizacao - 1, n_binarizacao - 1)
        b = inferencia_bayes_bin_general(a, n_binarizacao)
        alta = b[0]
        ultimo = lista1[-1]
        if alta > 0.5:
            prev = ultimo + (ultimo * taxa[0])
        else:
            prev = ultimo + (ultimo * taxa[1])
        prevs.append(prev)
        lista1.append(prev)
        contador += 1
    return prevs

def alfa(lista_valores):
    return sum(lista_valores) / len(lista_valores) if lista_valores else 0

def interpolador(lista_ano, lista_valores):
    data = datetime.today()
    ano_atual = data.year
    if not lista_ano: return [], []
    ano_completo = np.arange(lista_ano[0], ano_atual+1, 1)
    a = alfa(lista_valores)
    if a == 0: a = 1 
    anos_faltantes = list(set(ano_completo)-set(lista_ano))
    anos_faltantes.sort()
    valores_inter = np.interp(anos_faltantes, lista_ano, lista_valores)
    valores_inter = [(i/a)-((i*a)/100) for i in valores_inter]
    if len(valores_inter) >= 2:
        i = len(valores_inter)-1
        x = valores_inter[i]
        y = valores_inter[i-1]
        if x == y:
            valores_inter[-1] = (valores_inter[-1]/a)-((valores_inter[-1]*(2*a))/100)

    matriz = [lista_ano + anos_faltantes, lista_valores + [*valores_inter]]
    M = np.asarray(matriz)
    ordem = M[:, M[0].argsort()]
    ano_total = [int(i) for i in ordem[0]]
    valor_total = [round(j,4) for j in ordem[1]]
    return ano_total, valor_total

def previsao1(lista,ano1):
    ano = cp(ano1)
    nova_lista = cp(lista)
    if(len(lista)==0):
        return [0,0]
    if np.std(nova_lista)<=1:
        return [nova_lista[-1], nova_lista[-1]]

    if len(lista)<=3:
        aumento_lista = lista[0]
        aumento_ano = ano[0]
        lista.insert(0, aumento_lista)
        ano.insert(0, aumento_ano)
        if ano[0] == ano[1] or ano[1] == ano[2]:
            for i in range(len(ano)):
                ano[i] = ano[0]+(i)
        if ano[0] >= 2000:
            ano.insert(0, 2000)
            posicao_0 = lista[0]
            lista.insert(0, posicao_0)
            nova_ano, nova_lista = interpolador(ano, lista)
            Valfa = alfa(nova_lista)
            if Valfa == 1: Valfa = 0.99
            primeiro = nova_lista[-1] * (1 + (1-Valfa))
            segundo = primeiro * (1 + (1-Valfa))
            return [primeiro, segundo]
        else:
            return [0,0]

    if ano[0] == ano[1] or ano[1] == ano[2]:
        for i in range(len(ano)):
            ano[i] = ano[0]+(i)
        nova_ano = ano
    else:
        nova_ano, nova_lista = interpolador(ano, lista)

    coeficiente1 = nova_lista[-1] - nova_lista[-3]
    coeficiente2 = nova_lista[-2] - nova_lista[-4]
    if coeficiente1 == coeficiente2:
        delta = nova_lista[-1] - nova_lista[-2]
        prev1 = nova_lista[-1] + delta
        prev2 = prev1 + delta
    else:
        if np.std(nova_lista)<=1:
            prev1, prev2 = nova_lista[-1], nova_lista[-1]
        else:
            prev1, prev2 = naive_bayes(nova_lista, 2)
    return [round(prev1,3), round(prev2,3)]

    a3 = 3
    i3 = 1
    lista3 = cp(lista)
    while len(lista3) < 3:
        lista3 = lista3+lista3
    previsoes_media_movel3 = []
    final = lista3[(len(lista3)-a3):]
    while i3 <= n_de_prevs:
        x = (final[0]+final[1]+final[2])/a3
        previsoes_media_movel3.append(x)
        lista3.append(x)
        final = lista3[(len(lista3)-a3):]
        i3 +=1
    return(previsoes_media_movel3)

def media_movel4(lista, n_de_prevs):
    i = 1
    a = 4
    lista4 = cp(lista)
    while len(lista4) < 4:
        lista4 = lista4+lista4
    previsoes_media_movel4 = []
    final4 = lista4[(len(lista4)-a):]
    while i <= n_de_prevs:
        x = (final4[0]+final4[1]+final4[2]+final4[3])/a
        previsoes_media_movel4.append(x)
        lista4.append(x)
        final4 = lista4[(len(lista4)-a):]
        i +=1
    return(previsoes_media_movel4)

def media_movel12(lista, n_de_prevs):
    a = 12
    i = 1
    lista12 = cp(lista)
    previsoes_media_movel12 = []
    while len(lista12) < 12:
        lista12 = lista12+lista12
    final12 = lista12[(len(lista12)-a):]
    while i <= n_de_prevs:
        x = sum(final12[:])
        w = (x)/a
        previsoes_media_movel12.append(w)
        lista12.append(w)
        final12 = lista12[(len(lista12)-a):]
        i +=1
    return(previsoes_media_movel12)

def forecast_temp(historical_data: list, num_projections: int) -> list:
    """
    Esta função é o ponto de entrada que a API usa.
    Atualmente, ela chama 'naive_bayes'. Mude aqui se quiser usar outra.
    """
    if not historical_data:
        return [0.0] * num_projections
    
    return naive_bayes(historical_data, num_projections)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    cluster = LocalCluster()
    client = Client(cluster)
except Exception as e:
    logger.error(f"Falha ao iniciar o cluster Dask: {e}")
    client = None

celery_app = Celery(
    'forecast_tasks',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0'
)

app = FastAPI(title="API de Projeção de Séries Temporais", version="1.0.0")

class ProjecaoListaRequest(BaseModel):
    lista_historico: str = Field(..., description="Lista histórica em formato de string JSON. Ex: '[10, 11, 12]'")
    quantidade_projecoes: conint(gt=0) = Field(..., description="Número de projeções futuras a serem geradas.")
    @validator('lista_historico')
    def validate_lista_historico(cls, v):
        try:
            lista = json.loads(v)
            if not isinstance(lista, list): raise ValueError("O conteúdo do JSON deve ser uma lista.")
            if not lista: raise ValueError("A lista não pode estar vazia.")
            if not all(isinstance(item, (int, float)) for item in lista): raise ValueError("Todos os elementos da lista devem ser números (int ou float).")
            return v
        except json.JSONDecodeError: raise ValueError("Formato de string JSON inválido.")
        except ValueError as e: raise ValueError(str(e))

class ProjecaoDataframeRequest(BaseModel):
    quantidade_projecoes: conint(gt=0) = Field(..., description="Número de projeções futuras a serem geradas.")
    header: bool = Field(..., description="Indica se o arquivo CSV possui uma linha de cabeçalho.")
    index_col: bool = Field(..., description="Indica se a primeira coluna do CSV é um índice a ser ignorado.")
    page: conint(ge=1) = Field(1, description="Número da página para paginação de resultados.")
    page_size: conint(ge=1) = Field(10, description="Quantidade de linhas por página.")

class ProjecaoResponse(BaseModel):
    projecoes: List[Any]
    status: str = "completed"
    execution_time: Optional[float] = None
    total_pages: Optional[int] = None
    current_page: Optional[int] = None

class TaskSubmissionResponse(BaseModel):
    task_id: str
    status: str
    message: str

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[Any] = None

@celery_app.task(bind=True)
def process_forecast_lista(self, lista_historico: str, quantidade_projecoes: int):
    try:
        self.update_state(state='PROGRESS', meta={'status': 'Iniciando processamento...'})
        lista_original = json.loads(lista_historico)
        resultado = forecast_temp(lista_original, quantidade_projecoes)
        return {"projecoes": resultado, "status": "completed"}
    except Exception as e:
        self.update_state(state='FAILURE', meta={'exc': str(e)})
        logger.error(f"Task {self.request.id} falhou: {e}")
        raise e

@celery_app.task(bind=True)
def process_forecast_dataframe(self, file_path: str, quantidade_projecoes: int, header: bool, index_col: bool, page: int, page_size: int):
    try:
        self.update_state(state='PROGRESS', meta={'status': 'Lendo arquivo CSV...'})
        ddf = dd.read_csv(file_path, header=0 if header else None, assume_missing=True)
        if index_col: ddf = ddf.drop(ddf.columns[0], axis=1)
        total_rows = len(ddf)
        total_pages = math.ceil(total_rows / page_size)
        if page > total_pages and total_pages > 0: raise ValueError("Número da página fora do intervalo.")
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        ddf_paginated = ddf.loc[start_index:end_index - 1]
        self.update_state(state='PROGRESS', meta={'status': 'Calculando projeções...'})
        start_time = time.time()
        def apply_forecast(df):
            return df.apply(lambda row: forecast_temp(row.dropna().tolist(), quantidade_projecoes), axis=1)
        resultado = ddf_paginated.map_partitions(apply_forecast, meta=('object')).compute().tolist()
        execution_time = time.time() - start_time
        return {
            "projecoes": resultado, "execution_time": execution_time,
            "total_pages": total_pages, "current_page": page, "status": "completed"
        }
    except Exception as e:
        self.update_state(state='FAILURE', meta={'exc': str(e)})
        logger.error(f"Task {self.request.id} falhou: {e}")
        raise e
    finally:
        if os.path.exists(file_path): os.unlink(file_path)

@app.on_event("startup")
async def startup_event():
    if client: print(f"Dask Dashboard disponível em: {client.dashboard_link}")
    else: print("Dask não foi iniciado. Processamento de DataFrames pode ser lento.")
    print("FastAPI iniciado com sucesso.")

@app.post("/projecao_lista/", tags=["Projeções"])
async def projecao_por_lista(
    lista_historico: str = Form(...),
    quantidade_projecoes: int = Form(...),
    async_processing: bool = Form(False, description="Se True, a tarefa será processada em background.")
):
    try:
        request_data = ProjecaoListaRequest(lista_historico=lista_historico, quantidade_projecoes=quantidade_projecoes)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    
    if async_processing:
        task = process_forecast_lista.delay(request_data.lista_historico, request_data.quantidade_projecoes)
        return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content=TaskSubmissionResponse(task_id=task.id, status="processing", message="Tarefa de projeção de lista foi enfileirada.").dict())
    else:
        start_time = time.time()
        resultado = forecast_temp(json.loads(request_data.lista_historico), request_data.quantidade_projecoes)
        execution_time = time.time() - start_time
        return ProjecaoResponse(projecoes=resultado, execution_time=execution_time)


@app.post("/projecao_dataframe/", tags=["Projeções"])
async def projecao_por_dataframe(
    csv_dataframe: UploadFile = File(...),
    quantidade_projecoes: int = Form(...),
    header: bool = Form(...),
    index_col: bool = Form(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1),
    async_processing: bool = Form(False, description="Se True, a tarefa será processada em background.")
):
    try:
        request_data = ProjecaoDataframeRequest(quantidade_projecoes=quantidade_projecoes, header=header, index_col=index_col, page=page, page_size=page_size)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv", mode="wb") as tmp_file:
        content = await csv_dataframe.read()
        tmp_file.write(content)
        tmp_file_path = tmp_file.name
    if async_processing:
        task = process_forecast_dataframe.delay(tmp_file_path, request_data.quantidade_projecoes, request_data.header, request_data.index_col, request_data.page, request_data.page_size)
        return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content=TaskSubmissionResponse(task_id=task.id, status="processing", message="Tarefa de projeção de dataframe foi enfileirada.").dict())
    else:
        try:
            result_dict = process_forecast_dataframe.__wrapped__(process_forecast_dataframe, file_path=tmp_file_path, quantidade_projecoes=request_data.quantidade_projecoes, header=request_data.header, index_col=request_data.index_col, page=request_data.page, page_size=request_data.page_size)
            return ProjecaoResponse(**result_dict)
        except Exception as e:
            if os.path.exists(tmp_file_path): os.unlink(tmp_file_path)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.get("/tasks/{task_id}", response_model=TaskStatusResponse, tags=["Gerenciamento de Tarefas"])
async def get_task_status(task_id: str):
    task_result = celery_app.AsyncResult(task_id)
    response_data = {"task_id": task_id, "status": task_result.state, "result": task_result.result if task_result.state == 'SUCCESS' else str(task_result.info)}
    if task_result.state == 'PENDING': response_data["result"] = "Tarefa na fila, aguardando para ser executada."
    elif task_result.state == 'PROGRESS': response_data["result"] = task_result.info
    return TaskStatusResponse(**response_data)

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(status_code=exc.status_code, content={"error_type": "ClientError", "message": exc.detail, "status_code": exc.status_code})

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Erro interno não tratado: {exc}", exc_info=True)
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"error_type": "InternalServerError", "message": "Ocorreu um erro inesperado no servidor.", "status_code": 500})