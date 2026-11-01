use flate2::read::GzDecoder;
use pyo3::prelude::*;
use pyo3::types::PyList;
use quick_xml::events::Event;
use quick_xml::reader::Reader;
use std::fs::File;
use std::io::{BufRead, BufReader, Cursor};
use std::path::Path;

pub fn parse_xmltv_date(date_str: &str) -> String {
    let clean = date_str.trim();
    if clean.len() < 14 {
        return clean.to_string();
    }
    let b = clean.as_bytes();
    if !b[..14].iter().all(|c| c.is_ascii_digit()) {
        return clean.to_string();
    }
    let year = &clean[0..4];
    let month = &clean[4..6];
    let day = &clean[6..8];
    let hour = &clean[8..10];
    let minute = &clean[10..12];
    let second = &clean[12..14];

    let mut iso = format!("{year}-{month}-{day}T{hour}:{minute}:{second}");

    let rest = clean[14..].trim_start();
    if (rest.starts_with('+') || rest.starts_with('-')) && rest.len() >= 5 {
        let sign = &rest[0..1];
        let tz_hours = &rest[1..3];
        let tz_mins = &rest[3..5];
        if tz_hours.chars().all(|c| c.is_ascii_digit()) && tz_mins.chars().all(|c| c.is_ascii_digit()) {
            iso.push_str(sign);
            iso.push_str(tz_hours);
            iso.push(':');
            iso.push_str(tz_mins);
        }
    }
    iso
}

type RawProgramTuple = (
    String, // tvg_id
    String, // title
    String, // description
    String, // start_time (ISO)
    String, // end_time (ISO)
    String, // category
    String, // icon_url
);

fn parse_stream<R: BufRead>(
    py: Python<'_>,
    mut reader: Reader<R>,
    batch_size: usize,
    batch_callback: &Bound<'_, PyAny>,
    progress_callback: Option<&Bound<'_, PyAny>>,
) -> PyResult<usize> {
    reader.config_mut().trim_text(true);

    let mut buf = Vec::with_capacity(2048);
    let mut batch: Vec<RawProgramTuple> = Vec::with_capacity(batch_size);
    let mut total_count: usize = 0;

    let mut inside_programme = false;
    let mut current_tag = Vec::new();

    let mut channel_id = String::new();
    let mut start_raw = String::new();
    let mut stop_raw = String::new();
    let mut title = String::new();
    let mut desc = String::new();
    let mut category = String::new();
    let mut icon_src = String::new();

    loop {
        match reader.read_event_into(&mut buf) {
            Ok(Event::Start(ref e)) => {
                let name = e.name();
                if name.as_ref() == b"programme" {
                    inside_programme = true;
                    channel_id.clear();
                    start_raw.clear();
                    stop_raw.clear();
                    title.clear();
                    desc.clear();
                    category.clear();
                    icon_src.clear();

                    for attr in e.attributes().flatten() {
                        match attr.key.as_ref() {
                            b"channel" => {
                                channel_id = attr.unescape_value().unwrap_or_default().into_owned();
                            }
                            b"start" => {
                                start_raw = attr.unescape_value().unwrap_or_default().into_owned();
                            }
                            b"stop" => {
                                stop_raw = attr.unescape_value().unwrap_or_default().into_owned();
                            }
                            _ => {}
                        }
                    }
                } else if inside_programme {
                    current_tag = name.as_ref().to_vec();
                    if current_tag == b"icon" {
                        for attr in e.attributes().flatten() {
                            if attr.key.as_ref() == b"src" {
                                icon_src = attr.unescape_value().unwrap_or_default().into_owned();
                            }
                        }
                    }
                }
            }
            Ok(Event::Empty(ref e)) => {
                if inside_programme && e.name().as_ref() == b"icon" {
                    for attr in e.attributes().flatten() {
                        if attr.key.as_ref() == b"src" {
                            icon_src = attr.unescape_value().unwrap_or_default().into_owned();
                        }
                    }
                }
            }
            Ok(Event::Text(ref e)) => {
                if inside_programme {
                    let text = e.unescape().unwrap_or_default();
                    let trimmed = text.trim();
                    if !trimmed.is_empty() {
                        match current_tag.as_slice() {
                            b"title" => {
                                if !title.is_empty() {
                                    title.push(' ');
                                }
                                title.push_str(trimmed);
                            }
                            b"desc" => {
                                if !desc.is_empty() {
                                    desc.push(' ');
                                }
                                desc.push_str(trimmed);
                            }
                            b"category" => {
                                if !category.is_empty() {
                                    category.push(' ');
                                }
                                category.push_str(trimmed);
                            }
                            _ => {}
                        }
                    }
                }
            }
            Ok(Event::End(ref e)) => {
                let name = e.name();
                if name.as_ref() == b"programme" {
                    inside_programme = false;
                    current_tag.clear();

                    let start_iso = parse_xmltv_date(&start_raw);
                    let stop_iso = parse_xmltv_date(&stop_raw);

                    if !channel_id.is_empty() && !start_iso.is_empty() && !stop_iso.is_empty() {
                        if title.is_empty() {
                            title = "Programme".to_string();
                        }

                        batch.push((
                            std::mem::take(&mut channel_id),
                            std::mem::take(&mut title),
                            std::mem::take(&mut desc),
                            start_iso,
                            stop_iso,
                            std::mem::take(&mut category),
                            std::mem::take(&mut icon_src),
                        ));
                        total_count += 1;

                        if batch.len() >= batch_size {
                            let py_list = PyList::new(py, &batch)?;
                            batch_callback.call1((py_list,))?;
                            batch.clear();

                            if let Some(cb) = progress_callback {
                                cb.call1((total_count,))?;
                            }
                        }
                    }
                } else if inside_programme {
                    current_tag.clear();
                }
            }
            Ok(Event::Eof) => break,
            Err(e) => {
                return Err(pyo3::exceptions::PyValueError::new_err(format!(
                    "Erreur de parsing XMLTV : {}",
                    e
                )));
            }
            _ => {}
        }
        buf.clear();
    }

    if !batch.is_empty() {
        let py_list = PyList::new(py, &batch)?;
        batch_callback.call1((py_list,))?;
        batch.clear();
    }

    if let Some(cb) = progress_callback {
        cb.call1((total_count,))?;
    }

    Ok(total_count)
}

pub fn parse_epg_file(
    py: Python<'_>,
    file_path: &str,
    batch_size: usize,
    batch_callback: &Bound<'_, PyAny>,
    progress_callback: Option<&Bound<'_, PyAny>>,
) -> PyResult<usize> {
    let path = Path::new(file_path);
    if !path.exists() {
        return Err(pyo3::exceptions::PyFileNotFoundError::new_err(format!(
            "Fichier EPG introuvable : {}",
            file_path
        )));
    }

    let file = File::open(path)?;
    let mut buf_reader = BufReader::new(file);

    // Détection du magic number gzip 0x1f 0x8b
    let is_gzip = {
        let peek = buf_reader.fill_buf()?;
        peek.len() >= 2 && peek[0] == 0x1f && peek[1] == 0x8b
    } || file_path.ends_with(".gz");

    if is_gzip {
        let gz = GzDecoder::new(buf_reader);
        let reader = Reader::from_reader(BufReader::new(gz));
        parse_stream(py, reader, batch_size, batch_callback, progress_callback)
    } else {
        let reader = Reader::from_reader(buf_reader);
        parse_stream(py, reader, batch_size, batch_callback, progress_callback)
    }
}

pub fn parse_epg_bytes(
    py: Python<'_>,
    data: &[u8],
    batch_size: usize,
    batch_callback: &Bound<'_, PyAny>,
    progress_callback: Option<&Bound<'_, PyAny>>,
) -> PyResult<usize> {
    let is_gzip = data.len() >= 2 && data[0] == 0x1f && data[1] == 0x8b;

    if is_gzip {
        let gz = GzDecoder::new(Cursor::new(data));
        let reader = Reader::from_reader(BufReader::new(gz));
        parse_stream(py, reader, batch_size, batch_callback, progress_callback)
    } else {
        let reader = Reader::from_reader(Cursor::new(data));
        parse_stream(py, reader, batch_size, batch_callback, progress_callback)
    }
}
