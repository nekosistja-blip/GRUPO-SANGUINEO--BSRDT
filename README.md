# Consulta rápida de grupo sanguíneo

El sistema consulta por Carnet de Identidad en dos fuentes:

- `GRUPO SANGRE.xlsx`
- `DONANTESANT(1).xlsx`

En cada archivo relaciona `vamDonante.vdonCodDon` con `vamScreeni.vdonCodDon`.
El grupo mostrado se obtiene contando todas las donaciones válidas de ambos sistemas; si hay diferencias, se muestra el grupo que más se repite. Si existe empate, se usa el grupo de la donación más reciente.

## Rendimiento

`build_index.py` genera `donantes_index.sqlite`, un índice local por CI. La búsqueda normal se hace contra SQLite y es prácticamente inmediata. Al iniciar la aplicación se verifica la huella de los dos Excel; el índice solo se reconstruye si los archivos cambiaron.

## Actualizar datos

Reemplace los dos archivos Excel manteniendo sus nombres y reinicie la aplicación. También puede reconstruir manualmente con:

```bash
python build_index.py
```

## Ejecutar

```bash
streamlit run app.py
```
