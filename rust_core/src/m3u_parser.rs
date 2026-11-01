use chrono::Local;
use pyo3::prelude::*;
use pyo3::types::PyList;
use std::collections::HashMap;
use std::fs;
use std::path::Path;

pub fn read_m3u_file(file_path: &str) -> PyResult<String> {
    let path = Path::new(file_path);
    if !path.exists() {
        return Err(pyo3::exceptions::PyFileNotFoundError::new_err(format!(
            "Fichier M3U introuvable : {}",
            file_path
        )));
    }

    let bytes = fs::read(path)?;
    match String::from_utf8(bytes) {
        Ok(text) => Ok(text),
        Err(e) => {
            let bytes = e.into_bytes();
            let (cow, _, _) = encoding_rs::WINDOWS_1252.decode(&bytes);
            Ok(cow.into_owned())
        }
    }
}

/// Parse rapide des attributs key="val" sans regex
#[inline]
fn parse_extinf_line<'a>(line: &'a str) -> (HashMap<&'a str, &'a str>, &'a str) {
    let mut attrs = HashMap::new();
    let after_extinf = if let Some(stripped) = line.strip_prefix("#EXTINF:") {
        stripped.trim_start()
    } else {
        return (attrs, "");
    };

    // Trouver la virgule de séparation du titre en ignorant les virgules entre guillemets
    let mut in_quotes = false;
    let mut comma_idx = None;

    for (i, b) in after_extinf.char_indices() {
        if b == '"' {
            in_quotes = !in_quotes;
        } else if b == ',' && !in_quotes {
            comma_idx = Some(i);
            break;
        }
    }

    let (attr_part, title) = if let Some(idx) = comma_idx {
        (&after_extinf[..idx], after_extinf[idx + 1..].trim())
    } else {
        ("", after_extinf.trim())
    };

    // Parser les attributs key="value"
    let mut s = attr_part;
    while let Some(eq_pos) = s.find('=') {
        let before_eq = s[..eq_pos].trim_end();
        let key_start = before_eq
            .rfind(|c: char| c.is_whitespace() || c == ',')
            .map(|i| i + 1)
            .unwrap_or(0);
        let key = before_eq[key_start..].trim();

        let after_eq = s[eq_pos + 1..].trim_start();
        if let Some(stripped) = after_eq.strip_prefix('"') {
            if let Some(end_quote) = stripped.find('"') {
                let val = &stripped[..end_quote];
                if !key.is_empty() {
                    attrs.insert(key, val);
                }
                s = &stripped[end_quote + 1..];
                continue;
            }
        }
        break;
    }

    (attrs, title)
}

// Tuple retourné :
// 0: name
// 1: stream_url
// 2: logo_url
// 3: group_title
// 4: tvg_id
// 5: tvg_name
// 6: user_agent
// 7: http_referrer
// 8: stream_type
// 9: container_extension
// 10: added_at
// 11: extra_headers (HashMap)
type RawChannelTuple = (
    String,
    String,
    String,
    String,
    String,
    String,
    String,
    String,
    String,
    String,
    String,
    HashMap<String, String>,
);

pub fn parse_m3u_raw<'py>(
    py: Python<'py>,
    content: &str,
    progress_callback: Option<&Bound<'py, PyAny>>,
) -> PyResult<Bound<'py, PyList>> {
    let now_iso = Local::now().format("%Y-%m-%dT%H:%M:%S").to_string();

    let mut channels: Vec<RawChannelTuple> = Vec::with_capacity(content.len() / 150);
    let mut current_name = String::new();
    let mut current_group = "Général".to_string();
    let mut current_logo = String::new();
    let mut current_tvg_id = String::new();
    let mut current_tvg_name = String::new();
    let mut current_user_agent = String::new();
    let mut current_referrer = String::new();
    let mut current_added_at = String::new();
    let mut extra_headers: HashMap<String, String> = HashMap::new();

    let mut count: usize = 0;
    let vod_exts = [".mp4", ".mkv", ".avi", ".mov"];

    for raw_line in content.lines() {
        let line = raw_line.trim();
        if line.is_empty() {
            continue;
        }

        if line.starts_with("#EXTINF:") {
            let (attrs, title) = parse_extinf_line(line);

            // group-title
            let mut found_group = false;
            for (k, v) in &attrs {
                if k.eq_ignore_ascii_case("group-title") {
                    let vt = v.trim();
                    current_group = if vt.is_empty() {
                        "Général".to_string()
                    } else {
                        vt.to_string()
                    };
                    found_group = true;
                } else if k.eq_ignore_ascii_case("tvg-logo") {
                    current_logo = v.trim().to_string();
                } else if k.eq_ignore_ascii_case("tvg-id") {
                    current_tvg_id = v.trim().to_string();
                } else if k.eq_ignore_ascii_case("tvg-name") {
                    current_tvg_name = v.trim().to_string();
                } else if k.eq_ignore_ascii_case("user-agent") {
                    if current_user_agent.is_empty() {
                        current_user_agent = v.trim().to_string();
                    }
                } else if k.eq_ignore_ascii_case("added")
                    || k.eq_ignore_ascii_case("tvg-added")
                    || k.eq_ignore_ascii_case("date-added")
                {
                    let clean = v.trim();
                    if !clean.is_empty() && clean.chars().all(|c| c.is_ascii_digit()) {
                        if let Ok(ts) = clean.parse::<i64>() {
                            current_added_at = chrono::DateTime::from_timestamp(ts, 0)
                                .map(|dt| dt.format("%Y-%m-%dT%H:%M:%S").to_string())
                                .unwrap_or_else(|| now_iso.clone());
                        }
                    } else if !clean.is_empty() {
                        current_added_at = clean.replace(' ', "T");
                    }
                }
            }
            if !found_group {
                current_group = "Général".to_string();
            }

            if !title.is_empty() {
                current_name = title.to_string();
            } else if !current_tvg_name.is_empty() {
                current_name = current_tvg_name.clone();
            } else {
                current_name = "Sans nom".to_string();
            }
        } else if line.starts_with("#EXTGRP:") {
            if let Some((_, grp)) = line.split_once(':') {
                let grp_trimmed = grp.trim();
                if !grp_trimmed.is_empty() {
                    current_group = grp_trimmed.to_string();
                }
            }
        } else if line.starts_with("#EXTVLCOPT:") || line.starts_with("#EXTOPT:") {
            if let Some((_, opt)) = line.split_once(':') {
                let opt_trimmed = opt.trim();
                if let Some((k, v)) = opt_trimmed.split_once('=') {
                    let k_lower = k.to_lowercase().replace('-', "_");
                    if k_lower.contains("user_agent") {
                        current_user_agent = v.trim().to_string();
                    } else if k_lower.contains("http_referrer") || k_lower.contains("referrer") {
                        current_referrer = v.trim().to_string();
                    }
                }
            }
        } else if line.starts_with("#EXTHTTP:") {
            if let Some((_, json_str)) = line.split_once(':') {
                if let Ok(headers) = serde_json::from_str::<HashMap<String, String>>(json_str.trim()) {
                    extra_headers = headers;
                }
            }
        } else if !line.starts_with('#') {
            // URL du flux
            let stream_url = line.to_string();
            let lower_url = stream_url.to_lowercase();
            let mut stream_type = "live".to_string();
            let mut container_ext = String::new();

            let is_vod = vod_exts
                .iter()
                .any(|ext| lower_url.ends_with(ext) || lower_url.contains(&format!("{}?", ext)));

            if is_vod {
                if lower_url.contains("/series/") {
                    stream_type = "series".to_string();
                } else {
                    stream_type = "movie".to_string();
                }
                if let Some(ext_part) = lower_url.rsplit('.').next() {
                    container_ext = ext_part.split('?').next().unwrap_or("").to_string();
                }
            }

            let added_at = if !current_added_at.is_empty() {
                std::mem::take(&mut current_added_at)
            } else {
                now_iso.clone()
            };

            let name = if current_name.is_empty() {
                "Chaîne inconnue".to_string()
            } else {
                std::mem::take(&mut current_name)
            };

            channels.push((
                name,
                stream_url,
                std::mem::take(&mut current_logo),
                current_group.clone(),
                std::mem::take(&mut current_tvg_id),
                std::mem::take(&mut current_tvg_name),
                std::mem::take(&mut current_user_agent),
                std::mem::take(&mut current_referrer),
                stream_type,
                container_ext,
                added_at,
                std::mem::take(&mut extra_headers),
            ));

            count += 1;
            if let Some(cb) = progress_callback {
                if count % 500 == 0 {
                    let _ = cb.call1((count,));
                }
            }
        }
    }

    if let Some(cb) = progress_callback {
        let _ = cb.call1((count,));
    }

    PyList::new(py, channels)
}
