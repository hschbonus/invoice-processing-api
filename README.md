# Invoice Processing API

[![CI](https://github.com/hschbonus/invoice-processing-api/actions/workflows/ci.yml/badge.svg)](https://github.com/hschbonus/invoice-processing-api/actions/workflows/ci.yml)

API Python de démonstration qui reçoit des documents structurés, contrôle leurs
données et restitue un résultat normalisé. Le cas d'usage présenté est l'ingestion de
factures fournisseurs UBL fictives.

Il s'agit d'une étude de cas technique personnelle fondée sur un scénario et des
données fictifs. Le projet ne représente pas une mission client, ne constitue pas une
plateforme agréée et ne garantit aucune conformité fiscale.

## État actuel

Le socle FastAPI expose un endpoint de santé, un endpoint d'upload XML renvoyant
`202 Accepted` et un endpoint de consultation du résultat. Les documents et
traitements sont persistés avec SQLAlchemy. Une première version synchrone détecte les
factures UBL, extrait les données retenues et produit des anomalies structurées.
Celery/Redis reste une extension ultérieure du même pipeline.

## Besoin de marché observé

- La facture électronique française généralise les flux structurés et impose la
  réception à toutes les entreprises depuis le 1er septembre 2026 :
  https://www.economie.gouv.fr/tout-savoir-sur-la-facturation-electronique-pour-les-entreprises
- Les formats du socle sont UBL, CII et Factur-X :
  https://www.impots.gouv.fr/sites/default/files/media/1_metier/2_professionnel/EV/2_gestion/290_facturation_electronique/fiches_reforme/fiche-1_f_v.pdf
- Au 14 septembre 2026, Free-Work affiche 31 offres ou missions catégorisées FastAPI :
  https://www.free-work.com/fr/tech-it/jobs/fastapi
- La facturation électronique apparaît dans 44 offres ou missions, majoritairement
  fonctionnelles ou SI plutôt que strictement Python :
  https://www.free-work.com/fr/tech-it/jobs/facturation-electronique

Ces sources valident le problème et les compétences techniques, pas l'existence d'un
client pour ce projet ni l'intention d'en faire un produit commercial.

## Périmètre

### Inclus

- ingestion de factures UBL XML fictives ;
- traitement synchrone initial avec suivi d'état ;
- contrôles de cohérence et anomalies structurées ;
- résultat JSON récupérable par API ;
- tests, conteneurisation simple, CI et documentation OpenAPI ;
- ajout ultérieur et isolé de Celery/Redis si le parcours synchrone est maîtrisé.

### Hors périmètre

- transmission à l'administration ou à une plateforme agréée ;
- conseil fiscal ou garantie réglementaire ;
- comptabilité, paiement ou rapprochement bancaire ;
- interface frontend dédiée ;
- reconnaissance OCR propriétaire ;
- garantie de conformité UBL, Factur-X, CII ou EN 16931 ;
- RabbitMQ, Kubernetes et couche SQLAlchemy asynchrone.

## Stack

- FastAPI et Pydantic Settings ;
- PostgreSQL, SQLAlchemy synchrone et Alembic ;
- pytest et Ruff ;
- Docker Compose et GitHub Actions (à venir) ;
- Celery et Redis dans un second incrément seulement.

## Installation

```powershell
poetry install
```

## Utilisation

```powershell
poetry run uvicorn app.main:app --reload
```

La documentation interactive sera disponible sur `http://127.0.0.1:8000/docs`.

La base attendue par défaut est PostgreSQL. Sa connexion et le stockage local sont
configurables avec `DATABASE_URL`, `STORAGE_DIR` et `MAX_UPLOAD_BYTES` (voir
`.env.example`).

```powershell
poetry run alembic upgrade head
```

L'upload est disponible via `POST /v1/documents`. Il accepte actuellement un fichier
XML de 5 Mio maximum et renvoie les identifiants du document et du traitement. Le
traitement est exécuté dans la requête pour cette première version : le statut renvoyé
est `succeeded` ou `failed`. `GET /v1/jobs/{job_id}` restitue ensuite son état et son
résultat. Deux uploads au contenu identique réutilisent le document et le traitement
existants ; la réponse l'indique avec `deduplicated: true`.

```powershell
curl.exe -F "file=@samples/ubl/valid-invoice.xml;type=application/xml" `
  http://127.0.0.1:8000/v1/documents
```

## Sous-ensemble UBL pris en charge

Le parseur reconnaît une racine `Invoice` dans l'espace de noms officiel UBL et lit :

- numéro et date d'émission ;
- devise du document ;
- noms du fournisseur et du client ;
- montants net, taxe, brut et payable.

Il contrôle la présence de ces champs, le format de la date et de la devise, les
valeurs décimales et, dans le périmètre simplifié du démonstrateur, l'égalité
`net + taxe = brut`. Une facture lisible mais incohérente termine avec le statut
technique `succeeded` et le résultat métier `validation_status: invalid`. Un document
illisible ou qui n'est pas une facture UBL termine en `failed`.

Les trois fichiers de `samples/ubl/` sont fictifs et couvrent le cas valide pour ce
sous-ensemble, les anomalies métier et le XML mal formé. Leur structure reprend le
modèle de facture publié par OASIS :
https://docs.oasis-open.org/ubl/os-UBL-2.4/UBL-2.4.html

Le projet ne télécharge pas les schémas officiels et ne réalise pas de validation XSD,
EN 16931 ou fiscale.

## Vérification

```powershell
poetry run pytest
poetry run ruff check .
```

## Suivi

Le backlog canonique est celui du projet parent : `../BACKLOG.md`, phase 2 (`P2.*`).
