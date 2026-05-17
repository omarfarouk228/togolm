# TogoLM — Cahier des Charges

> **Première infrastructure IA open source centrée sur le Togo**
> Porteur : Omar Farouk KOUGBADA / KOF CORPORATION
> Version : 1.0 — Mai 2026

---

## Table des matières

1. [Contexte & Vision](#1-contexte--vision)
2. [Objectifs du projet](#2-objectifs-du-projet)
3. [Parties prenantes](#3-parties-prenantes)
4. [Périmètre du projet](#4-périmètre-du-projet)
5. [Architecture technique](#5-architecture-technique)
6. [Corpus de données](#6-corpus-de-données)
7. [Fine-tuning](#7-fine-tuning)
8. [Spécifications de l'API](#8-spécifications-de-lapi)
9. [Interface vitrine](#9-interface-vitrine)
10. [Modèle Open Source & Gouvernance](#10-modèle-open-source--gouvernance)
11. [Roadmap & Planning](#11-roadmap--planning)
12. [Ressources & Contraintes](#12-ressources--contraintes)
13. [Métriques de succès](#13-métriques-de-succès)

---

## 1. Contexte & Vision

### 1.1 Problème identifié

Le Togo dispose d'un volume croissant d'informations publiques — textes législatifs, données économiques, ressources éducatives, actualités, documents administratifs — mais ces données sont :

- **dispersées** sur des dizaines de sources hétérogènes,
- **non structurées** et difficilement exploitables par des systèmes IA,
- **absentes** des corpus d'entraînement des LLM internationaux (GPT, Gemini, Mistral...),
- **inaccessibles** aux citoyens, développeurs et institutions qui en ont besoin.

Il n'existe aujourd'hui aucune infrastructure IA publique centrée sur le contexte togolais.

### 1.2 Vision

**TogoLM** est la première infrastructure IA open source dédiée au Togo.

Elle a pour ambition de :

- constituer le **corpus de référence** sur le Togo (textes, données, langues),
- produire un **modèle de langage fine-tuné** sur ce corpus,
- exposer une **API publique** consommable par tout développeur ou institution,
- servir de **fondation technique** à l'écosystème IA togolais et ouest-africain francophone.

### 1.3 Positionnement

TogoLM se positionne comme :

> *"La couche IA de connaissance togolaise — ouverte, souveraine, contributive."*

Il ne s'agit pas d'un chatbot grand public, ni d'une app citoyenne isolée. C'est une **infrastructure réutilisable** sur laquelle d'autres produits peuvent être construits.

---

## 2. Objectifs du projet

### 2.1 Objectifs techniques

- Constituer un corpus togolais structuré d'au moins **50 000 documents** à la V1
- Déployer un pipeline RAG (Retrieval-Augmented Generation) fonctionnel
- Lancer un premier **fine-tuning** sur un modèle open source (Mistral 7B ou LLaMA 3)
- Exposer une API REST publique documentée
- Déployer une interface vitrine démontrant les capacités du modèle

### 2.2 Objectifs stratégiques

- Positionner TogoLM comme référence technique IA au Togo
- Créer un actif open source visible internationalement
- Ouvrir des opportunités de partenariat avec des institutions togolaises et organisations internationales
- Renforcer la crédibilité GDE et la visibilité internationale du porteur

### 2.3 Objectifs communautaires

- Fédérer une communauté de **contributeurs togolais et africains** autour du corpus
- Servir de projet pilote pour former des développeurs togolais à l'IA appliquée
- Inspirer des initiatives similaires dans d'autres pays francophones d'Afrique de l'Ouest

---

## 3. Parties prenantes

### 3.1 Porteur du projet

**Omar Farouk KOUGBADA**
- Google Developer Expert (GDE) Flutter & Dart
- Directeur Technique, KOF CORPORATION — Lomé, Togo
- Enseignant à l'Institut Africain d'Informatique (IAI)

### 3.2 Utilisateurs cibles

| Profil | Usage attendu |
|--------|---------------|
| Développeurs togolais | Intégration de l'API dans leurs applications |
| Startups africaines | Couche IA contextuelle pour leurs produits |
| Institutions gouvernementales | Accès structuré à la connaissance togolaise |
| Chercheurs & universitaires | Corpus et modèle pour travaux académiques |
| Organisations internationales | Données fiables sur le Togo |

### 3.3 Contributeurs potentiels

- Étudiants de l'IAI (Lomé)
- Membres de la communauté GDG Togo
- Développeurs de la diaspora togolaise
- Chercheurs NLP africains
- Contributeurs open source francophones

---

## 4. Périmètre du projet

### 4.1 Inclus dans la V1

- Pipeline de collecte et structuration des données togolaises
- Base vectorielle (corpus embeddings)
- Premier fine-tuning sur modèle open source
- API RAG publique (endpoints de base)
- Interface vitrine web
- Documentation publique complète
- Repository GitHub public avec contribution guidelines

### 4.2 Hors scope V1

- Application mobile
- Support vocal / ASR
- Fine-tuning sur langues locales (Ewé, Kabiyè) — prévu V2
- Dashboard analytics pour consommateurs API
- Authentification avancée / plans payants

### 4.3 Évolutions prévues

| Version | Contenu |
|---------|---------|
| V1 | Corpus + RAG + Fine-tuning V1 + API + Vitrine |
| V2 | Langues locales (Ewé, Kabiyè, Mina) + ASR |
| V3 | Fine-tuning avancé + modèle souverain hébergé localement |
| V4 | Marketplace de datasets togolais + API premium |

---

## 5. Architecture technique

### 5.1 Vue d'ensemble

```
┌─────────────────────────────────────────────────────────┐
│                     SOURCES DE DONNÉES                   │
│  Sites gouvernementaux · Presse · Textes légaux · IGE   │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                  PIPELINE DE COLLECTE                    │
│         Scrapers · Parsers · Nettoyage · Chunking       │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                   STOCKAGE & INDEXATION                  │
│     PostgreSQL + pgvector · Documents bruts · Metadata  │
└──────────┬──────────────────────────────┬───────────────┘
           │                              │
           ▼                              ▼
┌──────────────────┐           ┌──────────────────────────┐
│   FINE-TUNING    │           │        RAG ENGINE         │
│  Mistral 7B /    │           │  Embedding · Retrieval ·  │
│  LLaMA 3 8B      │           │  Reranking · Generation   │
└──────────┬───────┘           └──────────────┬───────────┘
           │                                  │
           └──────────────┬───────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────┐
│                      API PUBLIQUE                        │
│              FastAPI · REST · Authentification           │
└────────────────────────┬────────────────────────────────┘
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
┌─────────────────────┐   ┌─────────────────────────────┐
│  INTERFACE VITRINE  │   │    CONSOMMATEURS EXTERNES    │
│  Next.js  │   │  Apps · Institutions · Devs  │
└─────────────────────┘   └─────────────────────────────┘
```

### 5.2 Stack technique

| Composant | Technologie |
|-----------|-------------|
| Pipeline scraping | Python · Scrapy · BeautifulSoup · Celery |
| Stockage documents | PostgreSQL + pgvector (Supabase self-hosted) |
| Embeddings | Gemini Embeddings API / sentence-transformers |
| LLM RAG | Gemini 2.5 Flash (V1) → modèle fine-tuné (V2) |
| Fine-tuning | Hugging Face Transformers · LoRA / QLoRA |
| Modèle base | Mistral 7B Instruct ou LLaMA 3 8B |
| API | FastAPI · Python |
| Interface vitrine | Next.js|
| Hébergement | VPS (OVH / Hetzner) + GPU cloud (RunPod / Modal) |
| CI/CD | GitHub Actions |

---

## 6. Corpus de données

### 6.1 Sources identifiées

**Institutionnelles & gouvernementales**
- service-public.gouv.tg — démarches administratives
- presidence.gouv.tg — discours, textes officiels
- assemblee-nationale.tg — lois, décrets, débats
- mef.gouv.tg — données économiques et budgétaires
- inseed.tg — Institut National de la Statistique (données démographiques, économiques)

**Juridiques**
- Journal Officiel de la République Togolaise
- Codes (travail, commerce, civil, pénal)
- Textes réglementaires sectoriels

**Éducation & Recherche**
- Programmes scolaires officiels
- Publications universitaires togolaises
- Rapports de l'IAI et autres institutions

**Presse & Médias**
- togofirst.com
- icilome.com
- republicoftogo.com
- togoinfos.com

**Données sectorielles**
- Données santé (OMS Togo, Ministère Santé)
- Données agriculture (Ministère Agriculture)
- Rapports Banque Mondiale sur le Togo
- Rapports PNUD Togo

### 6.2 Langues couvertes

| Phase | Langues |
|-------|---------|
| V1 | Français |
| V2 | Ewé, Kabiyè, Mina |
| V3 | Hausa, Yoruba (extension régionale) |

### 6.3 Structure des données

```sql
-- Table principale des documents
CREATE TABLE documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source VARCHAR(255) NOT NULL,
  url TEXT,
  categorie VARCHAR(100),  -- legal, education, economie, sante, politique...
  sous_categorie VARCHAR(100),
  titre TEXT,
  contenu_brut TEXT NOT NULL,
  contenu_nettoye TEXT,
  langue VARCHAR(10) DEFAULT 'fr',
  date_publication DATE,
  date_collecte TIMESTAMP DEFAULT NOW(),
  date_maj TIMESTAMP,
  embedding vector(1536),
  metadata JSONB,
  statut VARCHAR(20) DEFAULT 'actif'
);

-- Index vectoriel
CREATE INDEX ON documents USING ivfflat (embedding vector_cosine_ops);
```

### 6.4 Pipeline de mise à jour

- Scraping initial : collecte complète des sources identifiées
- Scraping incrémental : mise à jour hebdomadaire automatisée via Celery Beat
- Validation manuelle : review communautaire pour les documents sensibles
- Versioning du corpus : tags Git sur chaque release majeure du dataset

---

## 7. Fine-tuning

### 7.1 Approche

Le fine-tuning commence en parallèle du RAG, dès la Phase 1, avec une approche progressive :

**Étape 1 — Instruction tuning (Mois 1-2)**
Adapter le modèle à répondre en contexte togolais avec des paires (question, réponse) générées à partir du corpus.

**Étape 2 — Domain adaptation (Mois 3-4)**
Fine-tuning sur le corpus brut togolais pour ancrer la connaissance dans le modèle.

**Étape 3 — RLHF léger (Mois 5-6)**
Feedback humain via la communauté pour améliorer la qualité des réponses.

### 7.2 Modèle de base

| Critère | Choix V1 |
|---------|----------|
| Modèle | Mistral 7B Instruct v0.3 |
| Méthode | QLoRA (4-bit quantization) |
| Framework | Hugging Face + PEFT |
| Infrastructure | RunPod / Modal (GPU A100 ou H100) |
| Durée estimée | 10-20h de compute par run |

### 7.3 Dataset de fine-tuning

Format instruction (Alpaca-style) :

```json
{
  "instruction": "Quelles sont les étapes pour créer une SARL au Togo ?",
  "input": "",
  "output": "Pour créer une SARL au Togo, vous devez suivre les étapes suivantes : 1. Rédiger les statuts de la société... [réponse complète basée sur le corpus]"
}
```

Objectif V1 : **5 000 à 10 000 paires** d'instruction générées semi-automatiquement et validées.

### 7.4 Publication

Le modèle fine-tuné sera publié sur **Hugging Face Hub** sous le namespace `togolm/`.

```
togolm/togolm-7b-v1
togolm/togolm-7b-instruct-v1
```

---

## 8. Spécifications de l'API

### 8.1 Base URL

```
https://api.togolm.ai/v1
```

### 8.2 Authentification

- V1 : API Key simple (header `X-API-Key`)
- V2 : OAuth2 + gestion des quotas par plan

### 8.3 Endpoints principaux

#### `POST /query`
Interroger le corpus togolais via RAG.

**Request**
```json
{
  "question": "Comment obtenir un acte de naissance au Togo ?",
  "categorie": "administratif",
  "langue": "fr",
  "max_tokens": 500
}
```

**Response**
```json
{
  "reponse": "Pour obtenir un acte de naissance au Togo...",
  "sources": [
    {
      "titre": "Service Public Togo — État Civil",
      "url": "https://service-public.gouv.tg/...",
      "score": 0.92
    }
  ],
  "modele": "togolm-7b-v1",
  "latence_ms": 340
}
```

#### `POST /embed`
Générer des embeddings via le modèle TogoLM.

**Request**
```json
{
  "texte": "Politique agricole du Togo 2025",
  "modele": "togolm-embed-v1"
}
```

#### `GET /categories`
Lister les catégories disponibles dans le corpus.

#### `GET /stats`
Statistiques publiques sur le corpus (nombre de documents, langues, dernière mise à jour).

### 8.4 Rate limiting

| Plan | Requêtes/jour | Tokens/mois |
|------|--------------|-------------|
| Free | 100 | 500 000 |
| Dev | 1 000 | 5 000 000 |
| Institution | Illimité | Illimité |

---

## 9. Interface vitrine

### 9.1 Objectif

Démontrer les capacités de TogoLM au grand public, aux développeurs et aux institutions via une interface web accessible et soignée.

### 9.2 Fonctionnalités V1

- **Playground** : tester l'API en temps réel (question → réponse avec sources)
- **Explorer le corpus** : parcourir les catégories et documents disponibles
- **Documentation** : guides d'intégration, exemples de code (Python, JS, Dart/Flutter)
- **Statistiques** : métriques publiques du corpus et du modèle
- **Contribuer** : guide pour contribuer au corpus ou au code

### 9.3 Stack

- **Framework** : Next.js
- **Style** : Tailwind CSS
- **Déploiement** : Vercel ou VPS KOF CORPORATION

### 9.4 Design

Interface sobre, professionnelle, bilingue français/anglais. Palette aux couleurs du drapeau togolais (vert, jaune, rouge) avec une typographie moderne.

---

## 10. Modèle Open Source & Gouvernance

### 10.1 Licence

| Composant | Licence |
|-----------|---------|
| Code (scrapers, API, pipeline) | MIT |
| Corpus de données | Creative Commons CC BY 4.0 |
| Modèle fine-tuné | Apache 2.0 |

### 10.2 Structure du repository GitHub

```
togolm/
├── README.md
├── CONTRIBUTING.md
├── LICENSE
├── corpus/
│   ├── scrapers/
│   ├── processors/
│   └── datasets/
├── api/
│   ├── app/
│   └── tests/
├── finetuning/
│   ├── scripts/
│   ├── configs/
│   └── datasets/
├── vitrine/
│   └── (Next.js app)
└── docs/
    ├── architecture.md
    ├── api-reference.md
    └── contributing.md
```

### 10.3 Contribution guidelines

- Issues GitHub pour signaler des sources manquantes ou erreurs dans le corpus
- Pull Requests pour contribuer des scrapers, corrections, améliorations
- Labels clairs : `corpus`, `api`, `finetuning`, `vitrine`, `bug`, `enhancement`
- Validation obligatoire par le maintainer pour les modifications du corpus

### 10.4 Gouvernance

- **Maintainer principal** : Omar Farouk KOUGBADA
- **Core contributors** : à recruter parmi les étudiants IAI et la communauté GDG Togo
- **Advisory board** : prévu V2 (institutions académiques, partenaires)

---

## 11. Roadmap & Planning

### Phase 1 — Fondations (Mois 1-2)

**Semaine 1-2**
- [ ] Création du repository GitHub public
- [ ] Rédaction du README et CONTRIBUTING
- [ ] Setup infrastructure (Supabase + pgvector)
- [ ] Premier scraper : service-public.gouv.tg

**Semaine 3-4**
- [ ] Scrapers : sources gouvernementales prioritaires
- [ ] Pipeline de nettoyage et chunking
- [ ] Génération des embeddings V1
- [ ] Début collecte dataset fine-tuning (paires instruction)

**Semaine 5-6**
- [ ] Scrapers : sources presse et juridiques
- [ ] RAG engine fonctionnel (FastAPI + pgvector)
- [ ] Premier run de fine-tuning (QLoRA sur RunPod)
- [ ] Tests internes

**Semaine 7-8**
- [ ] Corpus V1 : objectif 20 000 documents
- [ ] API V1 fonctionnelle (endpoints `/query`, `/stats`)
- [ ] Dataset fine-tuning V1 : 3 000 paires
- [ ] Évaluation qualitative du modèle

### Phase 2 — Lancement (Mois 3-4)

- [ ] Interface vitrine déployée
- [ ] Documentation complète
- [ ] Publication modèle sur Hugging Face Hub
- [ ] Annonce publique : LinkedIn, GitHub, communautés GDG
- [ ] Premier workshop TogoLM à l'IAI
- [ ] Corpus V1 finalisé : 50 000 documents
- [ ] Fine-tuning V2 (dataset enrichi)

### Phase 3 — Croissance (Mois 5-6)

- [ ] Onboarding premiers contributeurs externes
- [ ] Support langues locales V2 (Ewé, Kabiyè)
- [ ] API V2 (authentification, quotas, dashboard)
- [ ] Partenariats institutionnels (approche formelle)
- [ ] Soumission CFP conférences internationales sur TogoLM

### Phase 4 — Maturité (Mois 7-12)

- [ ] Modèle TogoLM souverain hébergé localement au Togo
- [ ] Marketplace datasets
- [ ] Extension West Africa LM (Bénin, Burkina, Niger)
- [ ] Modèle multilingue (français + langues locales)

---

## 12. Ressources & Contraintes

### 12.1 Temps disponible

- **1 jour par semaine** dédié à TogoLM
- Contributions ponctuelles via la communauté IAI et GDG

### 12.2 Budget infrastructure estimé

| Poste | Coût mensuel estimé |
|-------|---------------------|
| VPS hébergement API + DB | 20-40€/mois |
| GPU cloud (fine-tuning) | 50-150€/run |
| Gemini API (embeddings V1) | 10-30€/mois |
| Domaine + SSL | 15€/an |
| **Total V1** | **~100-200€/mois** |

### 12.3 Risques identifiés

| Risque | Probabilité | Mitigation |
|--------|-------------|------------|
| Données togolaises insuffisantes | Moyen | Élargir aux sources diaspora + organisations internationales |
| Qualité du corpus faible | Moyen | Pipeline de validation + review communautaire |
| Coût GPU élevé | Faible | QLoRA + modèles 7B + RunPod spot instances |
| Manque de contributeurs | Moyen | Ancrage IAI + workshops mensuels |
| Concurrence d'initiatives similaires | Faible | Différenciation technique et open source |

---

## 13. Métriques de succès

### 13.1 KPIs techniques (fin Phase 1)

- Corpus : ≥ 20 000 documents indexés
- API : latence moyenne < 2 secondes
- Fine-tuning : premier modèle publié sur Hugging Face
- Couverture : ≥ 10 sources togolaises actives

### 13.2 KPIs adoption (fin Phase 2)

- GitHub : ≥ 100 stars
- API : ≥ 50 développeurs enregistrés
- Hugging Face : ≥ 200 downloads du modèle
- Corpus : ≥ 50 000 documents

### 13.3 KPIs communautaires (fin Phase 3)

- Contributeurs actifs : ≥ 10
- Workshops organisés : ≥ 3
- Institutions partenaires : ≥ 2
- Mentions presse / conférences : ≥ 5

---

## Annexes

### A. Références

- [Mistral 7B](https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.3)
- [LLaMA 3 8B](https://huggingface.co/meta-llama/Meta-Llama-3-8B-Instruct)
- [pgvector](https://github.com/pgvector/pgvector)
- [Hugging Face PEFT / LoRA](https://github.com/huggingface/peft)
- [AI Hub Senegal](https://aihubsenegal.com) — référence régionale

### B. Contacts

- **Porteur** : Omar Farouk KOUGBADA — omar@kofcorporation.com
- **GitHub** : github.com/togolm *(à créer)*
- **Site** : togolm.ai *(à enregistrer)*

---

*Document maintenu par KOF CORPORATION — Lomé, Togo*
*Dernière mise à jour : Mai 2026*