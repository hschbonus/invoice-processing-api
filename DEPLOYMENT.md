# Déploiement de la démonstration — P2.15

État au 16 septembre 2026 : démonstration locale validée par Hervé sur les trois
échantillons ; protection par clé implémentée et testée ; hébergement à choisir.
P2.15 reste ouvert. Aucun service externe ni abonnement n'a été créé.

## Contrat de démonstration

- Étude de cas personnelle, uniquement des factures fictives.
- Documentation Swagger publique ; exécution avec clé communiquée séparément.
- Aucun secret dans Git, les supports publics ou les captures.
- Aucun accès Internet direct à PostgreSQL, Redis ou au worker.
- Un environnement dédié, sans données client ni base d'un autre projet.
- Ne pas présenter le sous-ensemble UBL comme une validation réglementaire.

## Choix d'hébergement à arbitrer

Le Docker Compose local partage `document_data` entre l'API et le worker. Une
plateforme qui isole le disque de chaque service ne permet pas de le transposer tel
quel : le worker ne pourrait pas lire les fichiers déposés par l'API.

### Option A — petit serveur Docker commun

Réutiliser la stack Compose sur une seule machine, avec un reverse proxy HTTPS,
un stockage partagé et PostgreSQL/Redis en réseau privé. Pas de nouvelle couche de
stockage dans l'application, mais maintenance système, sauvegardes et mises à jour
à assumer. Pertinent si un serveur maintenu existe déjà ; pas d'achat sans accord.
Le Compose actuel est uniquement local : ses identifiants et son port ouvert ne
doivent pas être repris tels quels en ligne.

### Option B — plateforme gérée

API et worker séparés, PostgreSQL géré, Redis privé et stockage objet accessible aux
deux services. Cela nécessite un adaptateur de stockage et des tests supplémentaires.
Ne pas contourner cette contrainte en lançant l'API et Celery dans un processus
unique ou en supprimant silencieusement le mode asynchrone de la démo.

Sources consultées le 16 septembre 2026 :

- Render : un disque ne peut pas être partagé entre services :
  https://render.com/docs/disks#disk-limitations-and-considerations
- Render : les disques persistants nécessitent un service payant :
  https://render.com/docs/disks
- Railway : volumes rattachés aux services et restrictions de montage :
  https://docs.railway.com/volumes/reference
- Coûts à vérifier au choix du fournisseur, sans estimation garantie :
  https://render.com/pricing et https://docs.railway.com/pricing/plans

## Conditions avant mise en ligne

1. Valider hébergeur, région, budget et accès au compte.
2. Configurer `APP_ENV=production` et une `API_KEY` aléatoire forte, ainsi que des
   secrets propres à la base et au broker ; tester la rotation de la clé.
3. Configurer HTTPS et le réseau privé ; limiter le corps HTTP avant son arrivée à
   l'application. La limite métier de 5 Mio ne protège pas à elle seule le parsing
   multipart ni la réception réseau d'une très grosse requête.
4. Restreindre les documents autorisés aux échantillons fictifs pour la démo
   publique, et borner uploads/reprises au point d'entrée. Ne jamais annoncer un
   service de dépôt de vraies factures.
5. Configurer une rétention courte et documenter la purge : arrêter l'ingestion et
   le worker, traiter/vider la file dédiée, supprimer ensemble les enregistrements
   et fichiers de cette seule démo, puis redémarrer et rejouer les trois cas.
   Aucun endpoint public de réinitialisation et aucune suppression large.
6. Vérifier accès refusé sans clé, upload valide, anomalie métier, XML illisible,
   déduplication, reprise, persistance après redémarrage et purge contrôlée.
7. Vérifier les logs sans secrets ni contenu de document, les alertes d'échec et
   le plafond de dépenses ; publier l'URL uniquement après cette recette.

## Critère de clôture

Une URL HTTPS réellement vérifiée, les trois cas exécutés sur le service hébergé,
les protections et la purge testées, et les commandes d'exploitation documentées.
Une configuration ou une image Docker construite ne suffisent pas à clore P2.15.
