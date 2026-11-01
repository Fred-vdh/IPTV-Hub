use fuzzy_matcher::skim::SkimMatcherV2;
use fuzzy_matcher::FuzzyMatcher;
use once_cell::sync::Lazy;
use std::sync::RwLock;

pub fn normalize(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for c in s.chars() {
        match c {
            'À'..='Ä' | 'à'..='ä' => out.push('a'),
            'È'..='Ë' | 'è'..='ë' => out.push('e'),
            'Ì'..='Ï' | 'ì'..='ï' => out.push('i'),
            'Ò'..='Ö' | 'ò'..='ö' => out.push('o'),
            'Ù'..='Ü' | 'ù'..='ü' => out.push('u'),
            'Ç' | 'ç' => out.push('c'),
            'Ñ' | 'ñ' => out.push('n'),
            'Ý' | 'ý' | 'ÿ' => out.push('y'),
            _ => {
                for lc in c.to_lowercase() {
                    out.push(lc);
                }
            }
        }
    }
    out
}

pub struct SearchChannelItem {
    pub id: i64,
    pub playlist_id: i64,
    pub stream_type: String,
    pub group_title: String,
    pub name: String,
    pub tvg_name: String,
    pub is_favorite: bool,
    pub is_enabled: bool,
    pub norm_name: String,
    pub norm_group: String,
    pub norm_tvg_name: String,
}

static SEARCH_INDEX: Lazy<RwLock<Vec<SearchChannelItem>>> = Lazy::new(|| RwLock::new(Vec::new()));
static MATCHER: Lazy<SkimMatcherV2> = Lazy::new(SkimMatcherV2::default);

pub fn update_search_index(
    raw_items: Vec<(
        i64,    // id
        i64,    // playlist_id
        String, // name
        String, // group_title
        String, // tvg_name
        String, // stream_type
        bool,   // is_favorite
        bool,   // is_enabled
    )>,
) {
    let mut new_index = Vec::with_capacity(raw_items.len());
    for (id, playlist_id, name, group_title, tvg_name, stream_type, is_favorite, is_enabled) in
        raw_items
    {
        let norm_name = normalize(&name);
        let norm_group = normalize(&group_title);
        let norm_tvg_name = normalize(&tvg_name);

        new_index.push(SearchChannelItem {
            id,
            playlist_id,
            stream_type,
            group_title,
            name,
            tvg_name,
            is_favorite,
            is_enabled,
            norm_name,
            norm_group,
            norm_tvg_name,
        });
    }

    let mut lock = SEARCH_INDEX.write().unwrap();
    *lock = new_index;
}

pub fn is_index_ready() -> bool {
    let lock = SEARCH_INDEX.read().unwrap();
    !lock.is_empty()
}

pub fn index_size() -> usize {
    let lock = SEARCH_INDEX.read().unwrap();
    lock.len()
}

pub fn clear_index() {
    let mut lock = SEARCH_INDEX.write().unwrap();
    lock.clear();
}

pub fn search_channels(
    query: &str,
    playlist_id: Option<i64>,
    stream_type: Option<&str>,
    group_title: Option<&str>,
    favorites_only: bool,
    only_enabled: bool,
    limit: usize,
    offset: usize,
) -> Vec<i64> {
    let norm_q = normalize(query.trim());
    if norm_q.is_empty() {
        return Vec::new();
    }

    let lock = SEARCH_INDEX.read().unwrap();
    if lock.is_empty() {
        return Vec::new();
    }

    let mut scored_results: Vec<(i64, i64)> = Vec::with_capacity(limit * 2);

    for item in lock.iter() {
        // Filtres
        if let Some(pid) = playlist_id {
            if item.playlist_id != pid {
                continue;
            }
        }
        if let Some(st) = stream_type {
            if st != "all" && item.stream_type != st {
                continue;
            }
        }
        if let Some(gt) = group_title {
            if gt != "Tous les groupes"
                && gt != "Toutes les chaînes"
                && gt != "Tous les films"
                && item.group_title != gt
            {
                continue;
            }
        }
        if favorites_only && !item.is_favorite {
            continue;
        }
        if only_enabled && !item.is_enabled {
            continue;
        }

        // Calcul du score de pertinence
        let mut best_score: Option<i64> = None;

        // 1. Égalité exacte
        if item.norm_name == norm_q {
            best_score = Some(20000);
        }
        // 2. Préfixe du nom (ex: "tf1" -> "TF1 HD")
        else if item.norm_name.starts_with(&norm_q) {
            let penalty = item.norm_name.len().min(500) as i64;
            best_score = Some(15000 - penalty);
        }
        // 3. Préfixe d'un mot dans le nom (ex: "hd" ou "sport" dans "Canal+ Sport")
        else if item.norm_name.split_whitespace().any(|w| w.starts_with(&norm_q)) {
            let penalty = item.norm_name.len().min(500) as i64;
            best_score = Some(12000 - penalty);
        }
        // 4. Sous-chaîne dans le nom
        else if let Some(pos) = item.norm_name.find(&norm_q) {
            let penalty = (pos * 10 + item.norm_name.len()).min(1000) as i64;
            best_score = Some(9000 - penalty);
        }
        // 5. Recherche floue (fuzzy) tolérante aux fautes dans le nom
        else if let Some(fuzzy_score) = MATCHER.fuzzy_match(&item.norm_name, &norm_q) {
            if fuzzy_score > 30 {
                best_score = Some(4000 + fuzzy_score);
            }
        }

        // Si aucun match sur le nom, recherche dans tvg_name ou group_title
        if best_score.is_none() {
            if !item.norm_tvg_name.is_empty() && item.norm_tvg_name.contains(&norm_q) {
                best_score = Some(2500);
            } else if !item.norm_group.is_empty() && item.norm_group.contains(&norm_q) {
                best_score = Some(1500);
            } else if let Some(fuzzy_score) = MATCHER.fuzzy_match(&item.norm_group, &norm_q) {
                if fuzzy_score > 40 {
                    best_score = Some(800 + fuzzy_score);
                }
            }
        }

        if let Some(score) = best_score {
            scored_results.push((score, item.id));
        }
    }

    // Tri par score décroissant
    scored_results.sort_unstable_by(|a, b| b.0.cmp(&a.0));

    scored_results
        .into_iter()
        .skip(offset)
        .take(limit)
        .map(|(_, id)| id)
        .collect()
}
