
 - [ ] TODO: Add config value for max_cached_protocols in SpeechStore
 - [ ] TODO: Extract relevant design documentation from docs/MERGED_SPEECH_CORPUS_* to docs/DESIGN.md
 - [ ] TODO: Move prebuilt_speech_index to pyriksprot
 - [ ] TODO: Replace use of Codecs with prebuilt_speech_index
 - [ ] FIXME: Add strict mode to alignment check in CorpusLoader
 - [ ] TODO: fixa get_config_store i Shape Shifter att följa samma mönster som i detta project (enklare unit testing)
 - [ ] FIXME: Try using category type for names?


# ÄNDRINGAR SENASTE TVÅ VECKORNA

1. Fokus på prestanda. Ändrat arkitekturen och flödet av data så att allt nu ligger server-side. Klienten hanterar nu inte längre ned stora datamängder, utan få precis det data som behövs för att via saker i UX. Gåt från synkrona, skicka allt, till server side paging.
2. Rätt stora ändringar i hur serverdelen hanterar data. Bland annat en ny indexerad struktur för att snabbare hämta index över talen, och även själva talen. Lagras nu lite mer som en indexerad databas. Har testat och optimera lagringsformatet (=> feather)
3. Hanteringen av anrop sker och hanteras är helt nytt. Nu används en mer robust "task queue" som gör att klienten inte längre hänger och väntar på data, den skickar istället en request, får direkt en ticket som sedan använs för polla status, hämta delmängder av och ladda ned hela datasetet.
4. Lite mer komplex deploy nu, tidigare 1 container är nu 4 (Redis + 2 x Celery)
5. Jag har kört mängder av benchmarks för att hitta flaskhalsar,  fixat många långsamma delar i systemet. Snålare minnesanvändning, vektoroperationer istället för loopar. Patchat paketet vi använder för att prata med CWB. etc. etc. Väldigt lite kod i kärna är opåverkad.
6. Wordtrends, KWIC och anföranden bör nu vara mycket snabbare. Även nedladdning, som nu sker streamat. Även ändrat så att det laddas ned komprimerat. Alla Zipfiler bör nu också ett manifest med versioner och sökparametrar.
7. De flesta gamla API:er finns kvar, men kan avvecklas när vi testat,
9. Stor uppstädning av källkoden. Mycket bättre struktur med tydligare flöden. Slutfört jobb som startades för ett halvår sedan.
10.  En större modul i systemet kommer från Westac-projektet, den är nu nedbantad och integrerad i Swedeb. 95% av koden är borttagen, resten delvis omskriven.
11. PDF:er visas nu från sidvisa PDF:er. Finns säkert edgecases här som kan förorsaka problem, om PDF saknas, eller om sidnummer inte stämmer. Det är sällan man träffar rätt sida.
12. Nedladdningar bör nu funka, och förhoppningsvis mycket snabbare. 
13. Jag gått igenom dokumentationen, den är mestadels AI-genererad, men med avsevärt med specifika instruktioner. Frontend är i princip helt dokumenterad.
14. Jag har uppdaterat alla paket (dependencies) i både frontend och backend. Vissa paket bumpades rejält, mer breaking changes. Det kan finns saker som inte är hanterat, främst då i frontend.
15. Fixat URL, client-side routing visas fortsatt, vilket är ok, men inte public och "#".
16. Har lagt in alternativ för antal träffar för KWIC. Finns nu mest för att testa. Kan läggas in för övriga tools också.
17. N-grams är inte rörd. Viss gemensam logik med KWIC kan ha påverkats. Är några dagars jobb att fixa n-grams. Jag vet inte om n-gramsbuggen följt med ut till staging.
18. Jag har ökat test code coverage, en del återstår att göra.
19. Jag har kör regressionstester mellan gammal och ny logik, det ser ut att vara ok.
20. Vi måste skapa qos tester asap, och innan vi driftsääter publikt.
21. 