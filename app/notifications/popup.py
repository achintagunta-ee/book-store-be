def popup(message: str, type: str = "success"):
    return {
        "popup": {
            "type": type,
            "message": message
        }
    }
