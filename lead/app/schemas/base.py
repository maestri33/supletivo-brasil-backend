from pydantic import BaseModel, ConfigDict
#TODO: Realoque esta funcao, sen sentido ter um diretório só pra este trecho de funcao

class APIModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
    )
