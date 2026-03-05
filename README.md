# 🏦 Conciliador Bancario

App web para conciliar extractos bancarios contra el Mayor de Cuentas del ERP.  
Soporta **BBVA**, **BNA (Nación)**, **Macro** y **Santander**.

---

## Instalación

### 1. Requisitos
- Python 3.10 o superior
- pip

### 2. Instalar dependencias
```bash
pip install streamlit pandas openpyxl xlrd
```

### 3. Correr la app
```bash
streamlit run app.py
```

Se abre automáticamente en `http://localhost:8501`

---

## Cómo usar

1. **Subí el extracto bancario** (`.xls` o `.xlsx`) — el banco se detecta automáticamente
2. **Subí el Mayor de Cuentas** (`.xlsx`) — exportado desde el ERP
3. Escribí el período (opcional, para el nombre del archivo descargado)
4. Hacé clic en **Ejecutar Conciliación**
5. Revisá los resultados en pantalla y descargá el Excel

---

## Formatos soportados

| Banco | Formato | Hoja | Fila datos |
|---|---|---|---|
| BBVA Frances | `.xls` / `.xlsx` | `Movimientos Históricos` | 8 en adelante |
| BNA (Nación) | `.xlsx` | `principal` | 15 en adelante |
| Macro | `.xlsx` | `principal` | 15 en adelante |
| Santander | `.xlsx` | `principal` | 15 en adelante |

El **Mayor de Cuentas** debe ser el export estándar del ERP (`.xlsx`), con las columnas `Fecha`, `Debe`, `Haber` a partir de la fila 8.

---

## Agregar un banco nuevo

Editá `parsers.py`:

1. Creá una función `parse_NOMBREBANCO(file) -> pd.DataFrame`  
   Tiene que devolver un DataFrame con las columnas:  
   `Fecha | Concepto | Comprobante | Credito | Debito | Importe`

2. Usá `_clean_df(df)` al final para normalizar tipos

3. Agregalo al diccionario `BANK_PARSERS`:
   ```python
   BANK_PARSERS = {
       "BBVA": parse_bbva,
       "BNA":  parse_bna,
       ...
       "MiBanco": parse_mibanco,   # ← acá
   }
   ```

4. Actualizá `detect_bank()` con la firma del archivo nuevo

---

## Estructura del proyecto

```
conciliador/
├── app.py          ← App Streamlit (interfaz)
├── parsers.py      ← Un parser por banco + auto-detección
├── engine.py       ← Motor de conciliación (lógica pura)
├── exporter.py     ← Generador del Excel de resultado
└── README.md
```

---

## Deploy en la nube (gratis)

### Streamlit Cloud
1. Subí la carpeta a un repo de GitHub
2. Entrá a [share.streamlit.io](https://share.streamlit.io)
3. Conectá el repo y deployá — listo, tenés una URL pública

### Railway / Render
Alternativas para más control. Necesitás un `requirements.txt`:
```
streamlit
pandas
openpyxl
xlrd
```
