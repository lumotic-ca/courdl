use serde::Serialize;

#[derive(Debug, Serialize)]
pub struct Envelope<T: Serialize> {
    pub ok: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub value: Option<T>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub code: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub message: Option<String>,
}

pub fn ok<T: Serialize>(value: T) -> Envelope<T> {
    Envelope {
        ok: true,
        value: Some(value),
        code: None,
        message: None,
    }
}

pub fn err<T: Serialize>(code: &str, message: impl Into<String>) -> Envelope<T> {
    Envelope {
        ok: false,
        value: None,
        code: Some(code.to_string()),
        message: Some(message.into()),
    }
}

pub type JsonEnvelope = Envelope<serde_json::Value>;

pub fn ok_json(value: serde_json::Value) -> JsonEnvelope {
    Envelope {
        ok: true,
        value: Some(value),
        code: None,
        message: None,
    }
}

pub fn err_json(code: &str, message: impl Into<String>) -> JsonEnvelope {
    err(code, message)
}
