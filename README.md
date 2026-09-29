**HurData** es un Dashboard Analítico de Gestión Académica diseñado para procesar, depurar y visualizar los datos operativos exportados por el sistema SIU Guaraní. Desarrollado en el ámbito del Instituto de Tecnología e Ingeniería de la Universidad Nacional de Hurlingham (UNaHur), el proyecto busca transformar reportes tabulares estáticos en información estratégica e interactiva.

Los reportes nativos del sistema (como las estadísticas de fin de cursada) suelen exportarse con formatos visuales pensados para la lectura humana, lo que dificulta el análisis masivo y programático. HurData resuelve este cuello de botella mediante un pipeline ETL (Extracción, Transformación y Carga) construido en Python, Pandas y FastAPI, automatizando la limpieza de archivos y preparándolos para su consumo en la web.

### ✨ Características Principales
* **Motor de Procesamiento Dinámico:** Limpia y normaliza automáticamente archivos Excel crudos del SIU, aislando los datos reales de los metadatos visuales.
* **Arquitectura Modular Orientada a Objetos:** Código backend estructurado profesionalmente, separando responsabilidades para facilitar el testing, la escalabilidad y el trabajo ágil en equipo.
* **Privacidad por Diseño (Privacy-First):** Configuración estricta de repositorios y entornos para garantizar que los archivos con datos sensibles de la universidad nunca se expongan en la nube pública.
* **API RESTful:** Exposición de endpoints rápidos y documentados, optimizados para alimentar de forma directa los gráficos interactivos del frontend.

# HurData - Backend 

Backend del Dashboard Analítico de Gestión Académica para la Universidad Nacional de Hurlingham (UNaHur). Desarrollado con Python, FastAPI y Pandas.

## Requisitos Previos
* Python 3.10 o superior.
* Git.

## Configuración del Entorno Local (Setup)

**1. Clonar el repositorio**
Abrir la terminal y ejecutar:
```bash
git clone [https://github.com/HurData-UNaHur/hurdata-pip-backend.git](https://github.com/HurData-UNaHur/hurdata-pip-backend.git)
cd hurdata-pip-backend
```

**2. Crear el entorno virtual**
Esto aísla las librerías del proyecto del resto de la computadora:
```bash
python -m venv venv
```

**3. Activar el entorno virtual**
* En Windows:
  ```bash
  venv\Scripts\activate
  ```
* En macOS / Linux:
  ```bash
  source venv/bin/activate
  ```
*(Deberían ver un `(venv)` al inicio de la línea en su terminal).*

**4. Instalar las dependencias**
Con el entorno activado, instalen todas las librerías (FastAPI, Pandas, etc.) usando el archivo de requerimientos:
```bash
pip install -r requirements.txt
```

## Gestión de Archivos Sensibles (Inputs)
Los reportes crudos del SIU Guaraní (archivos `.xlsx` o `.csv`) **NO** deben subirse a GitHub por cuestiones de privacidad de datos. 
Para probar los scripts ETL localmente, coloquen sus Excels dentro de la carpeta `files/` en la raíz del proyecto. El archivo `.gitignore` ya está configurado para omitir esta carpeta.