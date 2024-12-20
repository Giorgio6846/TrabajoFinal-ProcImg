from flask import Flask, request, jsonify, Response
from PIL import Image
import io
import os
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from time import gmtime, strftime
import pandas as pd
import uuid
from SiameseNetwork import ModelSM
import tools
from CM import FaceDepthVerification
import numpy as np

app = Flask(__name__)
app.secret_key=b'app'

limiter = Limiter(
    get_remote_address, 
    app=app, 
    default_limits=["1/second"]
)


class Data:
    def __init__(self):
        self.labelDepth = ""
        self.labelFace = ""
        
        self.Model = ModelSM()

sharedData = Data()
sharedData.Model.load_weights()

FaDeVe = FaceDepthVerification()

@app.route("/face-depth-data", methods=["POST"])
def cameraData():

    if "faceImage" not in request.files or "depthImage" not in request.files:
        return jsonify({"error": "Falta datos"}), 400

    depth_file = request.files["depthImage"]
    depth_image = Image.open(io.BytesIO(depth_file.read()))

    timeNow = str(strftime("%Y%m%d%H%M%S", gmtime()))

    if sharedData.labelFace != "" and sharedData.labelDepth != "":
        os.remove(
            os.path.join(
                os.path.dirname(__file__),
                "data",
                "tmp",
                sharedData.labelDepth,
            )
        )
        os.remove(
            os.path.join(
                os.path.dirname(__file__),
                "data",
                "tmp",
                sharedData.labelFace,
            )
        )
        
        sharedData.labelDepth = ""
        sharedData.labelFace = ""

    sharedData.labelDepth = f"DepthImage{timeNow}.png"
    sharedData.labelFace = f"FaceImage{timeNow}.jpg"

    depth_image = depth_image.rotate(270)
    depth_image.save(
        os.path.join(
            os.path.dirname(__file__),
            "data",
            "tmp",
            sharedData.labelDepth,
        )
    )

    colorImage_file = request.files["faceImage"]
    colorImage = Image.open(io.BytesIO(colorImage_file.read()))
    colorImage = colorImage.rotate(270)
    colorImage.save(
        os.path.join(
            os.path.dirname(__file__),
            "data",
            "tmp",
            sharedData.labelFace,
        )
    )

    return jsonify({"Message": "Datos recibidos con exito"})

@app.route("/face-depth-data", methods=["GET"])
def GUIData():
    if not (sharedData.labelFace != "" and sharedData.labelDepth != ""):
        print("Error: No hubieron imagenes iniciales")
        return jsonify({"Message": "No hubieron imagenes iniciales"})

    print(sharedData.labelFace)
    print(sharedData.labelDepth)

    with open(
        os.path.join(
            os.path.dirname(__file__),
            "data",
            "tmp",
            sharedData.labelFace,
        ), 
        "rb"
    ) as face_file:
        faceData = face_file.read()

    with open(
        os.path.join(
            os.path.dirname(__file__),
            "data",
            "tmp",
            sharedData.labelDepth,
        ),
        "rb",
    ) as depth_file:
        depthData = depth_file.read()

    boundary = uuid.uuid4().hex
    boundary_marker = f'--{boundary}'

    face_image_part = (
        (
            f"{boundary_marker}\r\n"
            "Content-Type: image/jpeg\r\n"
            'Content-Disposition: attachment; filename="faceImage.jpg"\r\n\r\n'
        ).encode()
        + faceData
        + b"\r\n"
    )

    depth_image_part = (
        (
            f"{boundary_marker}\r\n"
            "Content-Type: image/png\r\n"
            'Content-Disposition: attachment; filename="depthImage.png"\r\n\r\n'
        ).encode()
        + depthData
        + b"\r\n"
    )

    end_marker = f"{boundary_marker}--\r\n".encode()

    multipart_message = face_image_part + depth_image_part + end_marker

    return Response(multipart_message, mimetype=f"multipart/mixed; boundary={boundary}")

@app.route("/face-creation", methods=["POST"])
def userCreation():
    if not (sharedData.labelFace != "" and sharedData.labelDepth != ""):
        print("Error: No hubieron imagenes iniciales")
        return jsonify({"Message": "No hubieron imagenes iniciales"})

    jsonRequest = request.json

    print(jsonRequest.get('username'))

    dataframe = pd.read_csv(
        os.path.join(os.path.dirname(__file__), "data", "data.csv"), index_col=False
    )

    os.replace(
        os.path.join(
            os.path.dirname(__file__),
            "data",
            "tmp",
            sharedData.labelDepth,
        ),
        os.path.join(
            os.path.dirname(__file__),
            "data",
            sharedData.labelDepth,
        ),
    )

    os.replace(
        os.path.join(
            os.path.dirname(__file__),
            "data",
            "tmp",
            sharedData.labelFace,
        ),
        os.path.join(
            os.path.dirname(__file__),
            "data",
            sharedData.labelFace,
        ),
    )

    if jsonRequest.get('username') in dataframe["Username"].tolist():
        print("Already in dataframe") 
        return Response({"Message": "Ya esta en dataframe"}, 400)

    dataframe.loc[len(dataframe.index)] = [
        sharedData.labelFace,
        sharedData.labelDepth,
        f"{jsonRequest.get('username')}",
    ]

    sharedData.labelFace = ""
    sharedData.labelDepth = ""

    dataframe.to_csv(
        os.path.join(os.path.dirname(__file__), "data", "data.csv"), index=False
    )
    return jsonify({"Message": "Datos recibidos con exito"})


@app.route("/face-verification", methods=["GET"])
def userList():
    dataframe = pd.read_csv(os.path.join(
            os.path.dirname(__file__),
            "data",
            "data.csv"
        ), index_col=False)

    print(dataframe.head())
    jsonData = dataframe["Username"].to_json()

    return Response(jsonData,200)

@app.route("/face-verification", methods=["POST"])
def verifyUser():
    dataframe = pd.read_csv(
        os.path.join(os.path.dirname(__file__), "data", "data.csv"), index_col=False
    )

    jsonRequest = request.json
    print(jsonRequest.get("username"))

    usernameSearch = jsonRequest.get("username")

    data = dataframe[dataframe["Username"].str.contains(usernameSearch)]

    facePath =   f"./data/{data["Face"].iloc[0]}"
    depthPath =  f"./data/{data["Depth"].iloc[0]}"
    face1Path =  f"./data/tmp/{sharedData.labelFace}"
    depth1Path = f"./data/tmp/{sharedData.labelDepth}"

    tools.saveFaces(facePath, depthPath, face1Path, depth1Path)

    # Metodo Clasico
    percentageCM = FaDeVe.verify(
        facePath, depthPath, face1Path, depth1Path
    )

    # Metodo con DL
    percentageDL = sharedData.Model.predict_similarity(
        "./data/tmp/imgProc/F1.jpg",
        "./data/tmp/imgProc/D1.png",
        "./data/tmp/imgProc/F2.jpg",
        "./data/tmp/imgProc/D2.png"
    )

    print(percentageCM)
    print(type(percentageCM))

    if type(percentageCM) != np.float64:
        percentageCM = 0

    print(percentageCM)
    print(1-percentageDL)

    return jsonify({"PercentageDL": float(1-percentageDL), "PercentageClassic": float(percentageCM)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
