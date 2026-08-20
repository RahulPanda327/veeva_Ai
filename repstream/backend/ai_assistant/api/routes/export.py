# import io
# import csv
# import json
# import pandas as pd

# from fastapi import APIRouter, HTTPException
# from fastapi.responses import StreamingResponse
# from pydantic import BaseModel

# from results.result_store import get_query_results


# router = APIRouter(prefix="/download", tags=["Export"])


# class ExportRequest(BaseModel):
#     download_id: str
#     format: str


# @router.post("/export")
# def export_results(request: ExportRequest):

#     data = get_query_results(request.download_id)

#     if not data:
#         raise HTTPException(status_code=404, detail="Invalid download_id")

#     columns = data["columns"]
#     rows = data["rows"]

#     df = pd.DataFrame(rows, columns=columns)

#     # CSV Export
#     if request.format == "csv":

#         stream = io.StringIO()
#         df.to_csv(stream, index=False)

#         response = StreamingResponse(
#             iter([stream.getvalue()]),
#             media_type="text/csv"
#         )

#         response.headers[
#             "Content-Disposition"
#         ] = "attachment; filename=results.csv"

#         return response

#     # Excel Export
#     elif request.format == "xlsx":

#         stream = io.BytesIO()

#         with pd.ExcelWriter(stream, engine="openpyxl") as writer:
#             df.to_excel(writer, index=False)

#         stream.seek(0)

#         response = StreamingResponse(
#             stream,
#             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
#         )

#         response.headers[
#             "Content-Disposition"
#         ] = "attachment; filename=results.xlsx"

#         return response

#     # JSON Export
#     elif request.format == "json":

#         stream = io.StringIO()

#         json.dump(
#             df.to_dict(orient="records"),
#             stream,
#             indent=2,
#             default=str
#         )

#         response = StreamingResponse(
#             iter([stream.getvalue()]),
#             media_type="application/json"
#         )

#         response.headers[
#             "Content-Disposition"
#         ] = "attachment; filename=results.json"

#         return response

#     else:
#         raise HTTPException(status_code=400, detail="Unsupported format")

import io
import csv
import json
import pandas as pd

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from results.result_store import get_query_results


router = APIRouter(prefix="", tags=["Export"])   # ← CHANGED from "/download"


class ExportRequest(BaseModel):
    download_id: str
    format: str


@router.post("/download/export")
def export_results(request: ExportRequest):

    data = get_query_results(request.download_id)

    if not data:
        raise HTTPException(status_code=404, detail="Invalid download_id")

    columns = data["columns"]
    rows = data["rows"]
    df = pd.DataFrame(rows, columns=columns)

    if request.format == "csv":
        stream = io.StringIO()
        df.to_csv(stream, index=False)
        response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv")
        response.headers["Content-Disposition"] = "attachment; filename=results.csv"
        return response

    elif request.format == "xlsx":
        stream = io.BytesIO()
        with pd.ExcelWriter(stream, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)
        return Response(
            content=stream.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=results.xlsx"},
        )

    elif request.format == "json":
        stream = io.StringIO()
        json.dump(df.to_dict(orient="records"), stream, indent=2, default=str)
        response = StreamingResponse(iter([stream.getvalue()]), media_type="application/json")
        response.headers["Content-Disposition"] = "attachment; filename=results.json"
        return response

    else:
        raise HTTPException(status_code=400, detail="Unsupported format")


# ── NEW: GET endpoint for frontend download button ────────────────────────────
@router.get("/export/{download_id}")
def export_results_get(download_id: str, format: str = "csv"):
    data = get_query_results(download_id)

    if not data:
        raise HTTPException(status_code=404, detail="Invalid or expired download_id")

    columns = data["columns"]
    rows = data["rows"]
    df = pd.DataFrame(rows, columns=columns)

    if format == "xlsx":
        stream = io.BytesIO()
        with pd.ExcelWriter(stream, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)
        return Response(
            content=stream.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=results.xlsx"},
        )

    elif format == "json":
        stream = io.StringIO()
        json.dump(df.to_dict(orient="records"), stream, indent=2, default=str)
        response = StreamingResponse(iter([stream.getvalue()]), media_type="application/json")
        response.headers["Content-Disposition"] = "attachment; filename=results.json"
        return response

    else:  # default csv
        stream = io.StringIO()
        df.to_csv(stream, index=False)
        response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv")
        response.headers["Content-Disposition"] = "attachment; filename=results.csv"
        return response