# Git Usage
# Git Usage

## Little Elements Of Git
The main work that will be published is on a branch called main.
An important thing of git + github is that you have **local** branches and "syncronized" **remote branche**.
You do your work on your machine on your local branch *pippo*.
I do my work on my machine on my local branch *pippo*. 
Of course, my changes and your changes will modify locally the branch in different ways.
This will cause **conflicts** when trying to add our separate changes to the *remote branch*, which is on github.
How to solve this? Basically the first one that pushes is lucky, the other one has to handle merge conflicts (in the case they both touched the same file).
At the end of the conflict handling project, we all have a local copy of the branch identical to the one in github.

My Machine:
- pippo (and a history of changes)

Your Machine
- pippo (and a history of changes)

Github
- origin/pippo (!= dai pippo locali!!!!!!!!!!! si capisce perchè ha un nome diverso!!!! c'è origin!!!!!)

## Little element of Pull Request
Il branch origin/main contiene codice stabile e pronto alla release.
Ogni persona scrive su un branch dedicato ad una funzionalità, ad esempio il branch *origin/pippo* a cui è agganciato il mio branch *pippo* locale.
Quando la funzionalità è completa, bisogna:
- pullare da origin/main a main, così il tuo main locale è aggiornato con il origin
- mergiare main in pippo (locale). Questo procedimento può causare un merge conflict da risolvere. Se hai problemi, chiedi chi ha toccato il file su cui c'è il conflitto così ti aiuta.
- ora hai pippo in pari con main. E' l'ora di pusharlo su *origin/pippo*
- Ora *origin/pippo* (su github) è aggiornato con tutte le tue modifiche e in più è anche consistente con main. Dal browser, vai su github.com è richiedi una pullrequest da origin/pippo a origin/main. Questo permetterà di aggiungere le tue modifiche nel branch stabile. Se la UI non ti comunica merge conflicts, tutto ok. Se ti comunica merge conflicts, significa che qualcuno ha pushato delle modifiche su main mentre facevi passi. Semplicemente ripeti questa checklist.

## Creare un branch e commitare i tuoi cambiamenti
Quando ti viene assegnato un task, crea un branch locale. Ad esempio, devi lavorare sulla funzionalità *pippo*.
Creazione del branch:
```bash
git checkout -b pippo
```
Questo comando crea il branch pippo e ti sposta dal branch in cui ti trovi al branch pippo. Se pronto ad andare! 

⚠️⚠️⚠️ATTENZIONE⚠️⚠️⚠️: in questo momento non esiste ancora **origin/pippo**. Verra creato alla prima push request 

A questo punto farai delle modifiche. Tieni traccia delle tue modifiche con:
```bash
git add <file_da_aggiungere>
git commit -m "Ma se topolina si fa topolina, paperino si fa paperina, pippo cosa si fa?" 
```
Il commit è un messaggio che spiega cosa avete fatto. Fate quello che vi pare, non voglio lanciarmi in disquisizioni sull'utilità della cosa. Io personalmente scrivo che cosa ho fatto e non scrivo solo "update".
Se avete una ui che vi piace tanto usatela, di solito maschera la complessità di git, i don't care.

In generale, prima e dopo di una sequenza add-commit, vi consiglio di lanciare il seguente comando:
```bash
git status
```
o guardare la UI che state utilizzando. A volte se scrivere male il nome di un file, non viene aggiunto niente, e il commit che fate va a vuoto. 
In teoria se succede è scritto tutto nel terminale, ma capita spesso di ignorare i messaggi che vengono detti da questi due comandi.
Quindi state attenti e controllate che state realmente committando. Io uso una UI e mi è abbastanza semplice capire com'è andato il processo.

Ad un certo punto inizierete a provare panico all'idea che non avete ancora pushato. Per aggiornare il branch remoto su github dovete:
```bash
git push 
```
La prima volta che pushate da un branch appena creato vi fallirà. **LEGGETE L'OUTPUT!!!!!** vi dice qualcosa del tipo --set-upstream, fate quelloc dice. Il comando creerà un branch remoto su github con nome **origin/{nome-del-branch}** (in questo caso origin/pippo). Probabilmente qualche UI fa tutto automaticamente.

## Pubblicare i tuoi cambiamenti sul branch stabile
Hai completato la feature che ti è stata richiesta, è ora di aggiungere al branch stabile il tuo codice.
Seguendo quello che c'è scritto in  **Little element of Pull Request**,
bisogna
0. PUSHARE IL TUO BRANCH su ORIGIN
```bash
git push
```
1. Spostarsi su main
```bash
git checkout main
```
2. Pullare da main
```bash
git pull 
```
3. Mergiare main nel tuo branch locale *pippo*. Risolvi eventuali conflitti.
```bash
git checkout pippo
git merge main
```
4. Pusha il tuo pippo mergiato su origin/pippo
```bash
git push
```
5. Apri github e fai una pull request. Parla con qualcuno se non sai cosa sta succedendo. In generale, comunica al resto del team che stai facendo una pull request.
6. Ora le tue modifiche sono su origin/main


## Godot Limitations and Weird Behaviours

- Ogni asset si porta dietro un .import file con ifnromazioni per caricare
- il project file DEVE essere condiviso e contiene informazioni su caratteristiche schermo e così via
- le scene hashano in qualche maniera alcune cose, spesso non c'è stato nessun cambiamento a parte l'hash
- godot quando vede un cambiamento su disco  ti chiede se vuoi dumpare il contenuto della ram su disco o caricar il disco in ram, questo ha causato tanti problemi la prima jam


## Panic Buttons
- se durante un merge il tuo branch locale si sputtana o non esce mai dai confliti. Relax. Crea un nuovo branch a partire da origin/pippo, se sei stato bravo e prima del merge hai uploadato tutto non avrai nessun problemi. RIprendi il merge da questo nuovo branch che hai creato.