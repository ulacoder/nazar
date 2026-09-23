/* Lightweight frontend-only localization. API/database values stay canonical. */
(function () {
  const translations = {
    en: {
      "app.title": "NAZAR · Classroom observation",
      "nav.live": "Live", "nav.sessions": "Sessions", "nav.events": "Events",
      "nav.analytics": "Analytics", "nav.system": "System", "nav.settings": "Settings",
      "nav.main": "Main navigation", "nav.theme": "Toggle theme", "nav.language": "Language",
      "theme.light": "Light", "theme.dark": "Dark",
      "status.connecting": "Connecting", "status.cameraConnected": "Camera connected",
      "status.cameraOffline": "Camera offline", "status.videoPlaying": "Video playing",
      "status.videoEnded": "Video ended", "status.videoUnavailable": "Video unavailable",
      "status.connected": "Connected", "status.disconnected": "Disconnected",
      "status.checking": "Checking source", "status.sourcePending": "Source status pending",
      "status.processing": "Processing frames", "status.waiting": "Waiting for frames",
      "status.videoFinished": "Video finished", "status.unavailable": "Unavailable",
      "live.eyebrow": "Your workspace is ready to go.", "live.title": "Classroom overview.",
      "live.subtitle": "Anonymous observations from your local camera or video file.",
      "live.startSession": "Start session", "live.stopSession": "Stop session",
      "live.visiblePeople": "Visible people", "live.trackNote": "Anonymous temporary tracks",
      "live.aiProcessing": "AI processing", "live.waitingFrame": "Waiting for a frame",
      "live.currentSession": "Current session", "live.inactive": "Inactive",
      "live.startLessonExam": "Start a Lesson or Exam", "live.recording": "Recording",
      "live.onAir": "On air", "live.off": "Off", "live.framesCaptured": "{count} frames captured",
      "live.timelapseInactive": "Timelapse not active", "live.liveSource": "Live source",
      "live.sourceSubtitle": "Pose boxes, temporary IDs and confirmed states",
      "live.peopleInView": "People in view", "live.currentAttributes": "Current confirmed attributes",
      "live.waitingOutput": "Waiting for source and model output.",
      "live.noPeople": "No people currently visible.", "live.recentEvents": "Recent events",
      "live.confirmedSession": "Confirmed observations in this session", "common.seeAll": "See all →",
      "live.systemGlance": "System at a glance", "live.actualHealth": "Actual local health and model status",
      "live.details": "Details →", "live.noEvents": "No events yet.",
      "live.noConfirmedState": "No confirmed state", "live.boxes": "Boxes", "live.skeleton": "Skeleton",
      "live.states": "States", "live.live": "LIVE", "live.person": "Person #{id}",
      "sessions.eyebrow": "Review past work", "sessions.title": "Sessions.",
      "sessions.subtitle": "Lesson and Exam history, summaries, events and timelapses.",
      "sessions.all": "All sessions", "sessions.date": "Date / time", "sessions.duration": "Duration",
      "sessions.people": "People", "sessions.events": "Events", "sessions.timelapse": "Timelapse",
      "sessions.available": "Available", "sessions.open": "Open →", "sessions.loading": "Loading sessions…",
      "sessions.noData": "No sessions saved yet.", "sessions.temporaryTracks": "temporary tracks",
      "sessions.eventTimeline": "Event timeline", "sessions.noSessionEvents": "No confirmed events in this session.",
      "sessions.noTimelapse": "No timelapse available for this session.", "sessions.close": "Close ×",
      "events.eyebrow": "Observable behavior only", "events.title": "Events.",
      "events.subtitle": "Temporally confirmed changes linked to anonymous tracks.",
      "events.allSessions": "All sessions", "events.allModes": "All modes", "events.allTypes": "All types",
      "events.clearFilters": "Clear filters", "events.time": "Time", "events.date": "Date", "events.session": "Session",
      "events.person": "Person", "events.observedState": "Observed state", "events.modelScore": "Model score",
      "events.loading": "Loading events…", "events.noData": "No matching events.",
      "events.inVideo": "{time} s in video", "events.personId": "Person #{id}",
      "analytics.eyebrow": "Descriptive, not evaluative", "analytics.title": "Analytics.",
      "analytics.subtitle": "Counts and trends from saved sessions and events.",
      "analytics.distribution": "Event distribution", "analytics.byMode": "Sessions by mode",
      "analytics.overTime": "Events over time", "analytics.daily": "Daily counts from stored observations",
      "analytics.noEvents": "No event data yet.", "analytics.noSessions": "No sessions yet.",
      "analytics.lesson": "Lesson", "analytics.exam": "Exam", "analytics.day": "Day",
      "system.eyebrow": "Measured locally", "system.title": "System status.",
      "system.subtitle": "Camera, AI, tracking and hardware diagnostics.", "system.inputSource": "Input source",
      "system.type": "Type", "system.status": "Status", "system.file": "File", "system.videoPosition": "Video position",
      "system.resolution": "Resolution", "system.requestedFps": "Requested FPS", "system.actualFps": "Actual FPS",
      "system.error": "Error", "system.aiPipeline": "AI pipeline", "system.aiFps": "AI FPS",
      "system.poseFps": "Pose FPS", "system.actionsFps": "Actions FPS", "system.headFps": "Head FPS",
      "system.poseLatency": "Pose latency", "system.actionsLatency": "Actions latency", "system.headLatency": "Head latency",
      "system.totalLatency": "Total latency", "system.poseCalls": "Pose calls", "system.models": "Models",
      "system.hardware": "Hardware", "system.cpu": "CPU usage", "system.ram": "RAM usage",
      "system.processRam": "Process RAM", "system.cuda": "CUDA", "system.gpu": "GPU",
      "system.gpuUtilization": "GPU utilization", "system.vramInUse": "VRAM in use", "system.vramTotal": "VRAM total",
      "system.trackingRecording": "Tracking & recording", "system.visibleTracks": "Visible tracks",
      "system.activeTracks": "Active tracks", "system.framesRecorded": "Frames recorded",
      "system.output": "Output", "system.thresholds": "0.39 / 0.41 · V2 config, not V4 validated",
      "system.loaded": "Loaded", "system.unavailable": "Unavailable", "system.inactive": "Inactive",
      "settings.eyebrow": "Your local setup", "settings.title": "Settings.",
      "settings.subtitle": "Camera or video input, inference, overlays, events and timelapse.",
      "settings.save": "Save settings", "settings.inputSource": "Input source", "settings.source": "Source",
      "settings.camera": "Camera", "settings.video": "Video file", "settings.videoPath": "Video file path",
      "settings.cameraIndex": "Camera index", "settings.width": "Width", "settings.height": "Height",
      "settings.requestedFps": "Requested FPS", "settings.ai": "AI", "settings.aiInterval": "AI interval (seconds)",
      "settings.poseConfidence": "Pose confidence", "settings.actionsModel": "Actions model",
      "settings.headModel": "Head model", "settings.overlaysEvents": "Overlays & events",
      "settings.eventDuration": "Event minimum duration (s)", "settings.eventCooldown": "Event cooldown (s)",
      "settings.timelapse": "Timelapse", "settings.enableRecording": "Enable recording",
      "settings.includeOverlays": "Include overlays", "settings.captureInterval": "Capture interval (s)",
      "settings.outputFps": "Output FPS", "settings.thresholdNote": "Actions thresholds: READING 0.39, WRITING 0.41. These are reference-runner defaults from the supplied V2 config, not validated V4 thresholds. The V4 checkpoint separately records 0.5. NAZAR does not tune these values.",
      "modal.start": "Start a session", "modal.choose": "Select how you want to label this observation period.",
      "modal.lessonDescription": "Observe classroom activity", "modal.examDescription": "Record factual exam observations",
      "modal.note": "Only anonymous temporary track IDs are stored.", "common.refresh": "↻ Refresh",
      "common.noData": "No data", "common.requestFailed": "Request failed ({status})", "common.saved": "Settings saved.",
      "common.sessionStarted": "{mode} session started", "common.sessionSaved": "Session saved",
      "common.perFrame": "{value} ms per AI frame", "common.resolutionUnknown": "Resolution unknown",
      "common.cameraFps": "{value} camera FPS", "common.videoPosition": "{position} / {duration} s",
      "common.videoUnknownDuration": "—", "common.cameraDisconnected": "Camera disconnected",
      "common.videoUnavailable": "Video unavailable", "common.timelapseRecording": "Recording",
      "state.READING": "Reading", "state.WRITING": "Writing", "state.SITTING": "Sitting",
      "state.STANDING": "Standing", "state.HAND_RAISED": "Hand raised", "state.HAND_RAISED_LEFT": "Left hand raised",
      "state.HAND_RAISED_RIGHT": "Right hand raised", "state.BOTH_HANDS_RAISED": "Both hands raised",
      "state.LOOKING_FORWARD": "Looking forward", "state.LOOKING_LEFT": "Looking left",
      "state.LOOKING_RIGHT": "Looking right", "state.LOOKING_UP": "Looking up", "state.LOOKING_DOWN": "Looking down",
      "state.TURNED_BACK": "Turned back", "state.UNKNOWN_HEAD": "Unknown head direction"
    },
    kk: {
      "app.title": "NAZAR · Сыныпты бақылау", "nav.live": "Тікелей", "nav.sessions": "Сессиялар", "nav.events": "Оқиғалар", "nav.analytics": "Талдау", "nav.system": "Жүйе", "nav.settings": "Баптаулар", "nav.main": "Негізгі навигация", "nav.theme": "Тақырыпты ауыстыру", "nav.language": "Тіл", "theme.light": "Жарық", "theme.dark": "Қараңғы", "status.connecting": "Қосылуда", "status.cameraConnected": "Камера қосылды", "status.cameraOffline": "Камера қолжетімсіз", "status.videoPlaying": "Бейне ойнатылуда", "status.videoEnded": "Бейне аяқталды", "status.videoUnavailable": "Бейне қолжетімсіз", "status.connected": "Қосылған", "status.disconnected": "Ажыратылған", "status.checking": "Көз тексерілуде", "status.sourcePending": "Көз күйі күтілуде", "status.processing": "Кадрлар өңделуде", "status.waiting": "Кадрлар күтілуде", "status.videoFinished": "Бейне аяқталды", "status.unavailable": "Қолжетімсіз",
      "live.eyebrow": "Жұмыс кеңістігі дайын.", "live.title": "Сынып көрінісі.", "live.subtitle": "Жергілікті камерадан немесе бейнефайлдан алынған аноним бақылау.", "live.startSession": "Сессияны бастау", "live.stopSession": "Сессияны тоқтату", "live.visiblePeople": "Көрінген адамдар", "live.trackNote": "Аноним уақытша тректер", "live.aiProcessing": "AI өңдеуі", "live.waitingFrame": "Кадр күтілуде", "live.currentSession": "Ағымдағы сессия", "live.inactive": "Белсенді емес", "live.startLessonExam": "Сабақ немесе емтиханды бастау", "live.recording": "Жазу", "live.onAir": "Жазылуда", "live.off": "Өшірулі", "live.framesCaptured": "{count} кадр жазылды", "live.timelapseInactive": "Таймлапс белсенді емес", "live.liveSource": "Тікелей көз", "live.sourceSubtitle": "Позалар, уақытша ID және расталған күйлер", "live.peopleInView": "Көріністегі адамдар", "live.currentAttributes": "Ағымдағы расталған күйлер", "live.waitingOutput": "Көз бен модель нәтижесі күтілуде.", "live.noPeople": "Қазір көрінетін адам жоқ.", "live.recentEvents": "Соңғы оқиғалар", "live.confirmedSession": "Осы сессиядағы расталған бақылаулар", "common.seeAll": "Барлығын көру →", "live.systemGlance": "Жүйеге шолу", "live.actualHealth": "Жергілікті нақты күй және модель күйі", "live.details": "Толығырақ →", "live.noEvents": "Оқиға жоқ.", "live.noConfirmedState": "Расталған күй жоқ", "live.boxes": "Қораптар", "live.skeleton": "Қаңқа", "live.states": "Күйлер", "live.live": "ТІКЕЛЕЙ", "live.person": "Адам #{id}",
      "sessions.eyebrow": "Өткен жұмысты қарау", "sessions.title": "Сессиялар.", "sessions.subtitle": "Сабақ және емтихан тарихы, қорытындылар, оқиғалар мен таймлапстар.", "sessions.all": "Барлық сессия", "sessions.date": "Күн / уақыт", "sessions.duration": "Ұзақтығы", "sessions.people": "Адамдар", "sessions.events": "Оқиғалар", "sessions.timelapse": "Таймлапс", "sessions.available": "Қолжетімді", "sessions.open": "Ашу →", "sessions.loading": "Сессиялар жүктелуде…", "sessions.noData": "Сақталған сессия жоқ.", "sessions.temporaryTracks": "уақытша трек", "sessions.eventTimeline": "Оқиғалар хронологиясы", "sessions.noSessionEvents": "Бұл сессияда расталған оқиға жоқ.", "sessions.noTimelapse": "Бұл сессияда таймлапс жоқ.", "sessions.close": "Жабу ×",
      "events.eyebrow": "Тек байқалатын әрекет", "events.title": "Оқиғалар.", "events.subtitle": "Аноним тректерге байланыстырылған уақыт бойынша расталған өзгерістер.", "events.allSessions": "Барлық сессия", "events.allModes": "Барлық режим", "events.allTypes": "Барлық түр", "events.clearFilters": "Сүзгілерді тазалау", "events.time": "Уақыт", "events.date": "Күн", "events.session": "Сессия", "events.person": "Адам", "events.observedState": "Бақыланған күй", "events.modelScore": "Модель ұпайы", "events.loading": "Оқиғалар жүктелуде…", "events.noData": "Сәйкес оқиға жоқ.", "events.inVideo": "Бейненің {time} с", "events.personId": "Адам #{id}",
      "analytics.eyebrow": "Сипаттамалық, бағалау емес", "analytics.title": "Талдау.", "analytics.subtitle": "Сақталған сессиялар мен оқиғалардың саны және үрдістері.", "analytics.distribution": "Оқиғалар бөлінісі", "analytics.byMode": "Режим бойынша сессиялар", "analytics.overTime": "Уақыт бойынша оқиғалар", "analytics.daily": "Сақталған бақылаулардың күндік саны", "analytics.noEvents": "Оқиға дерегі жоқ.", "analytics.noSessions": "Сессия жоқ.", "analytics.lesson": "Сабақ", "analytics.exam": "Емтихан", "analytics.day": "Күн",
      "system.eyebrow": "Жергілікті өлшем", "system.title": "Жүйе күйі.", "system.subtitle": "Камера, AI, трекинг және жабдық диагностикасы.", "system.inputSource": "Кіріс көзі", "system.type": "Түрі", "system.status": "Күйі", "system.file": "Файл", "system.videoPosition": "Бейне орны", "system.resolution": "Ажыратымдылық", "system.requestedFps": "Сұралған FPS", "system.actualFps": "Нақты FPS", "system.error": "Қате", "system.aiPipeline": "AI конвейері", "system.aiFps": "AI FPS", "system.poseFps": "Поза FPS", "system.actionsFps": "Әрекет FPS", "system.headFps": "Бас FPS", "system.poseLatency": "Поза кідірісі", "system.actionsLatency": "Әрекет кідірісі", "system.headLatency": "Бас кідірісі", "system.totalLatency": "Жалпы кідіріс", "system.poseCalls": "Поза шақырулары", "system.models": "Модельдер", "system.hardware": "Жабдық", "system.cpu": "CPU қолданылуы", "system.ram": "RAM қолданылуы", "system.processRam": "Процесс RAM", "system.cuda": "CUDA", "system.gpu": "GPU", "system.gpuUtilization": "GPU қолданылуы", "system.vramInUse": "Қолданылған VRAM", "system.vramTotal": "Жалпы VRAM", "system.trackingRecording": "Трекинг және жазу", "system.visibleTracks": "Көрінетін тректер", "system.activeTracks": "Белсенді тректер", "system.framesRecorded": "Жазылған кадрлар", "system.output": "Нәтиже", "system.thresholds": "0.39 / 0.41 · V2 конфигурациясы, V4 үшін расталмаған", "system.loaded": "Жүктелген", "system.unavailable": "Қолжетімсіз", "system.inactive": "Белсенді емес",
      "settings.eyebrow": "Жергілікті баптау", "settings.title": "Баптаулар.", "settings.subtitle": "Камера немесе бейне кірісі, инференс, қабаттар, оқиғалар және таймлапс.", "settings.save": "Баптауларды сақтау", "settings.inputSource": "Кіріс көзі", "settings.source": "Көз", "settings.camera": "Камера", "settings.video": "Бейнефайл", "settings.videoPath": "Бейнефайл жолы", "settings.cameraIndex": "Камера индексі", "settings.width": "Ені", "settings.height": "Биіктігі", "settings.requestedFps": "Сұралған FPS", "settings.ai": "AI", "settings.aiInterval": "AI аралығы (секунд)", "settings.poseConfidence": "Поза сенімділігі", "settings.actionsModel": "Әрекет моделі", "settings.headModel": "Бас моделі", "settings.overlaysEvents": "Қабаттар және оқиғалар", "settings.eventDuration": "Оқиғаның ең аз ұзақтығы (с)", "settings.eventCooldown": "Оқиға үзілісі (с)", "settings.timelapse": "Таймлапс", "settings.enableRecording": "Жазуды қосу", "settings.includeOverlays": "Қабаттарды қосу", "settings.captureInterval": "Түсіру аралығы (с)", "settings.outputFps": "Шығыс FPS", "settings.thresholdNote": "Әрекет шектері: READING 0.39, WRITING 0.41. Бұл жеткізілген V2 конфигурациясынан алынған reference-runner әдепкілері, V4 үшін расталмаған. V4 checkpoint метадеректерінде 0.5 бөлек көрсетілген. NAZAR бұл мәндерді баптамайды.",
      "modal.start": "Сессияны бастау", "modal.choose": "Осы бақылау кезеңін қалай белгілеу керегін таңдаңыз.", "modal.lessonDescription": "Сынып әрекетін бақылау", "modal.examDescription": "Емтихан бақылауларын жазу", "modal.note": "Тек аноним уақытша трек ID сақталады.", "common.refresh": "↻ Жаңарту", "common.noData": "Дерек жоқ", "common.requestFailed": "Сұрау қатесі ({status})", "common.saved": "Баптаулар сақталды.", "common.sessionStarted": "{mode} сессиясы басталды", "common.sessionSaved": "Сессия сақталды", "common.perFrame": "AI кадрына {value} мс", "common.resolutionUnknown": "Ажыратымдылық белгісіз", "common.cameraFps": "{value} камера FPS", "common.videoPosition": "{position} / {duration} с", "common.videoUnknownDuration": "—", "common.cameraDisconnected": "Камера ажыратылған", "common.videoUnavailable": "Бейне қолжетімсіз", "common.timelapseRecording": "Жазылуда",
      "state.READING": "Оқып отыр", "state.WRITING": "Жазып отыр", "state.SITTING": "Отыр", "state.STANDING": "Тұр", "state.HAND_RAISED": "Қол көтерді", "state.HAND_RAISED_LEFT": "Сол қол көтерілді", "state.HAND_RAISED_RIGHT": "Оң қол көтерілді", "state.BOTH_HANDS_RAISED": "Екі қол көтерілді", "state.LOOKING_FORWARD": "Алға қарап отыр", "state.LOOKING_LEFT": "Солға қарап отыр", "state.LOOKING_RIGHT": "Оңға қарап отыр", "state.LOOKING_UP": "Жоғары қарап отыр", "state.LOOKING_DOWN": "Төмен қарап отыр", "state.TURNED_BACK": "Артқа бұрылды", "state.UNKNOWN_HEAD": "Бас бағыты анықталмады"
    },
    ru: {
      "app.title": "NAZAR · Наблюдение за классом", "nav.live": "Онлайн", "nav.sessions": "Сессии", "nav.events": "События", "nav.analytics": "Аналитика", "nav.system": "Система", "nav.settings": "Настройки", "nav.main": "Основная навигация", "nav.theme": "Сменить тему", "nav.language": "Язык", "theme.light": "Светлая", "theme.dark": "Тёмная", "status.connecting": "Подключение", "status.cameraConnected": "Камера подключена", "status.cameraOffline": "Камера недоступна", "status.videoPlaying": "Видео воспроизводится", "status.videoEnded": "Видео завершено", "status.videoUnavailable": "Видео недоступно", "status.connected": "Подключено", "status.disconnected": "Отключено", "status.checking": "Проверка источника", "status.sourcePending": "Ожидание состояния источника", "status.processing": "Обработка кадров", "status.waiting": "Ожидание кадров", "status.videoFinished": "Видео завершено", "status.unavailable": "Недоступно",
      "live.eyebrow": "Рабочее пространство готово.", "live.title": "Обзор класса.", "live.subtitle": "Анонимные наблюдения с локальной камеры или видеофайла.", "live.startSession": "Начать сессию", "live.stopSession": "Остановить сессию", "live.visiblePeople": "Людей видно", "live.trackNote": "Анонимные временные треки", "live.aiProcessing": "Обработка AI", "live.waitingFrame": "Ожидание кадра", "live.currentSession": "Текущая сессия", "live.inactive": "Неактивна", "live.startLessonExam": "Начать урок или экзамен", "live.recording": "Запись", "live.onAir": "Записывается", "live.off": "Выкл.", "live.framesCaptured": "Записано кадров: {count}", "live.timelapseInactive": "Таймлапс не активен", "live.liveSource": "Источник", "live.sourceSubtitle": "Позы, временные ID и подтверждённые состояния", "live.peopleInView": "Люди в кадре", "live.currentAttributes": "Текущие подтверждённые состояния", "live.waitingOutput": "Ожидание источника и результата модели.", "live.noPeople": "Сейчас людей не видно.", "live.recentEvents": "Последние события", "live.confirmedSession": "Подтверждённые наблюдения этой сессии", "common.seeAll": "Показать все →", "live.systemGlance": "Состояние системы", "live.actualHealth": "Фактическое состояние и модели", "live.details": "Подробнее →", "live.noEvents": "Событий пока нет.", "live.noConfirmedState": "Нет подтверждённого состояния", "live.boxes": "Рамки", "live.skeleton": "Скелет", "live.states": "Состояния", "live.live": "ЭФИР", "live.person": "Человек #{id}",
      "sessions.eyebrow": "История работы", "sessions.title": "Сессии.", "sessions.subtitle": "История уроков и экзаменов, сводки, события и таймлапсы.", "sessions.all": "Все сессии", "sessions.date": "Дата / время", "sessions.duration": "Длительность", "sessions.people": "Люди", "sessions.events": "События", "sessions.timelapse": "Таймлапс", "sessions.available": "Доступен", "sessions.open": "Открыть →", "sessions.loading": "Загрузка сессий…", "sessions.noData": "Сохранённых сессий нет.", "sessions.temporaryTracks": "временных треков", "sessions.eventTimeline": "Хронология событий", "sessions.noSessionEvents": "В этой сессии нет подтверждённых событий.", "sessions.noTimelapse": "Таймлапс для этой сессии недоступен.", "sessions.close": "Закрыть ×",
      "events.eyebrow": "Только наблюдаемое поведение", "events.title": "События.", "events.subtitle": "Подтверждённые во времени изменения, связанные с анонимными треками.", "events.allSessions": "Все сессии", "events.allModes": "Все режимы", "events.allTypes": "Все типы", "events.clearFilters": "Очистить фильтры", "events.time": "Время", "events.date": "Дата", "events.session": "Сессия", "events.person": "Человек", "events.observedState": "Наблюдаемое состояние", "events.modelScore": "Оценка модели", "events.loading": "Загрузка событий…", "events.noData": "Подходящих событий нет.", "events.inVideo": "{time} с видео", "events.personId": "Человек #{id}",
      "analytics.eyebrow": "Описательно, не оценочно", "analytics.title": "Аналитика.", "analytics.subtitle": "Количество и динамика сохранённых сессий и событий.", "analytics.distribution": "Распределение событий", "analytics.byMode": "Сессии по режимам", "analytics.overTime": "События во времени", "analytics.daily": "Дневное количество сохранённых наблюдений", "analytics.noEvents": "Данных о событиях пока нет.", "analytics.noSessions": "Сессий пока нет.", "analytics.lesson": "Урок", "analytics.exam": "Экзамен", "analytics.day": "День",
      "system.eyebrow": "Локальные измерения", "system.title": "Состояние системы.", "system.subtitle": "Диагностика камеры, AI, трекинга и оборудования.", "system.inputSource": "Источник", "system.type": "Тип", "system.status": "Состояние", "system.file": "Файл", "system.videoPosition": "Позиция видео", "system.resolution": "Разрешение", "system.requestedFps": "Запрошенный FPS", "system.actualFps": "Фактический FPS", "system.error": "Ошибка", "system.aiPipeline": "AI-конвейер", "system.aiFps": "AI FPS", "system.poseFps": "Pose FPS", "system.actionsFps": "Actions FPS", "system.headFps": "Head FPS", "system.poseLatency": "Задержка Pose", "system.actionsLatency": "Задержка Actions", "system.headLatency": "Задержка Head", "system.totalLatency": "Общая задержка", "system.poseCalls": "Вызовы Pose", "system.models": "Модели", "system.hardware": "Оборудование", "system.cpu": "Использование CPU", "system.ram": "Использование RAM", "system.processRam": "RAM процесса", "system.cuda": "CUDA", "system.gpu": "GPU", "system.gpuUtilization": "Использование GPU", "system.vramInUse": "Использовано VRAM", "system.vramTotal": "Всего VRAM", "system.trackingRecording": "Трекинг и запись", "system.visibleTracks": "Видимые треки", "system.activeTracks": "Активные треки", "system.framesRecorded": "Записано кадров", "system.output": "Результат", "system.thresholds": "0.39 / 0.41 · конфигурация V2, не проверено для V4", "system.loaded": "Загружена", "system.unavailable": "Недоступна", "system.inactive": "Неактивно",
      "settings.eyebrow": "Локальная настройка", "settings.title": "Настройки.", "settings.subtitle": "Камера или видео, инференс, слои, события и таймлапс.", "settings.save": "Сохранить настройки", "settings.inputSource": "Источник ввода", "settings.source": "Источник", "settings.camera": "Камера", "settings.video": "Видеофайл", "settings.videoPath": "Путь к видеофайлу", "settings.cameraIndex": "Индекс камеры", "settings.width": "Ширина", "settings.height": "Высота", "settings.requestedFps": "Запрошенный FPS", "settings.ai": "AI", "settings.aiInterval": "Интервал AI (секунды)", "settings.poseConfidence": "Уверенность Pose", "settings.actionsModel": "Модель Actions", "settings.headModel": "Модель Head", "settings.overlaysEvents": "Слои и события", "settings.eventDuration": "Минимальная длительность события (с)", "settings.eventCooldown": "Пауза событий (с)", "settings.timelapse": "Таймлапс", "settings.enableRecording": "Включить запись", "settings.includeOverlays": "Включать слои", "settings.captureInterval": "Интервал захвата (с)", "settings.outputFps": "Выходной FPS", "settings.thresholdNote": "Пороги Actions: READING 0.39, WRITING 0.41. Это значения reference-runner из конфигурации V2, не проверенные пороги V4. В метаданных V4 отдельно указано 0.5. NAZAR не настраивает эти значения.",
      "modal.start": "Начать сессию", "modal.choose": "Выберите, как обозначить этот период наблюдения.", "modal.lessonDescription": "Наблюдать активность класса", "modal.examDescription": "Записывать фактические наблюдения экзамена", "modal.note": "Сохраняются только анонимные временные ID треков.", "common.refresh": "↻ Обновить", "common.noData": "Нет данных", "common.requestFailed": "Ошибка запроса ({status})", "common.saved": "Настройки сохранены.", "common.sessionStarted": "Сессия «{mode}» начата", "common.sessionSaved": "Сессия сохранена", "common.perFrame": "{value} мс на AI-кадр", "common.resolutionUnknown": "Разрешение неизвестно", "common.cameraFps": "{value} FPS камеры", "common.videoPosition": "{position} / {duration} с", "common.videoUnknownDuration": "—", "common.cameraDisconnected": "Камера отключена", "common.videoUnavailable": "Видео недоступно", "common.timelapseRecording": "Запись",
      "state.READING": "Чтение", "state.WRITING": "Письмо", "state.SITTING": "Сидит", "state.STANDING": "Стоит", "state.HAND_RAISED": "Поднята рука", "state.HAND_RAISED_LEFT": "Поднята левая рука", "state.HAND_RAISED_RIGHT": "Поднята правая рука", "state.BOTH_HANDS_RAISED": "Подняты обе руки", "state.LOOKING_FORWARD": "Смотрит вперёд", "state.LOOKING_LEFT": "Смотрит влево", "state.LOOKING_RIGHT": "Смотрит вправо", "state.LOOKING_UP": "Смотрит вверх", "state.LOOKING_DOWN": "Смотрит вниз", "state.TURNED_BACK": "Повернулся назад", "state.UNKNOWN_HEAD": "Направление головы не определено"
    }
  };

  translations.en["system.day"] = "Date";
  translations.kk["system.day"] = "Күн";
  translations.ru["system.day"] = "Дата";
  ["live.title", "sessions.title", "events.title", "analytics.title", "system.title", "settings.title"].forEach((key) => {
    Object.values(translations).forEach((catalog) => { catalog[key] = (catalog[key] || "").replace(/[.]$/, ""); });
  });
  Object.assign(translations.en, {
    "settings.sourceManager":"Input source manager", "settings.cameraDevice":"Camera", "settings.noCameras":"No cameras discovered", "settings.rescanCameras":"Rescan cameras", "settings.preview":"Preview", "settings.chooseVideo":"Choose video file", "settings.dropVideo":"Drop a video here", "settings.videoReady":"Video ready", "settings.duration":"Duration", "settings.resolution":"Resolution", "settings.frameRate":"Frame rate", "settings.fileSize":"File size", "settings.uploading":"Uploading video…", "settings.endSessionSource":"End the active session before changing the source.", "settings.cameraPreviewUnavailable":"Camera preview unavailable", "settings.videoImportFailed":"Video import failed", "settings.sourceSwitchBlocked":"Source switching is blocked during an active session.",
    "metadata.teacher":"Teacher", "metadata.className":"Class / group", "metadata.subject":"Subject", "metadata.notes":"Notes (optional)",
    "metadata.confirm":"Start observation", "metadata.forMode":"Session type: {mode}", "metadata.proctor":"Teacher / Proctor", "metadata.classGroup":"Class / Group", "metadata.subjectExam":"Subject / Exam", "metadata.startLesson":"Start Lesson", "metadata.startExam":"Start Exam", "detail.back":"← Back to sessions",
    "detail.overview":"Overview", "detail.analytics":"Analytics", "detail.allTracks":"All temporary tracks",
    "detail.peopleOverTime":"People visible over time", "detail.byTrack":"Events by temporary track",
    "detail.occurrences":"Confirmed event occurrences, not time spent in each state.",
    "detail.noDurations":"State end times were not saved, so confirmed durations cannot be calculated.",
    "detail.noSamples":"No recorded samples for this session.", "detail.seek":"Seek ↗",
    "detail.seekApprox":"Event-to-timelapse seeking is approximate; capture intervals and dropped frames can shift alignment.",
    "detail.seekUnavailable":"Seek timing is unavailable for this older session."
  });
  Object.assign(translations.kk, {
    "settings.sourceManager":"Кіріс көзін басқару", "settings.cameraDevice":"Камера", "settings.noCameras":"Камера табылмады", "settings.rescanCameras":"Камераларды қайта іздеу", "settings.preview":"Алдын ала көру", "settings.chooseVideo":"Бейнефайлды таңдау", "settings.dropVideo":"Бейнені осы жерге тастаңыз", "settings.videoReady":"Бейне дайын", "settings.duration":"Ұзақтығы", "settings.resolution":"Ажыратымдылығы", "settings.frameRate":"Кадр жиілігі", "settings.fileSize":"Файл өлшемі", "settings.uploading":"Бейне жүктелуде…", "settings.endSessionSource":"Көзді ауыстыру үшін белсенді сеансты аяқтаңыз.", "settings.cameraPreviewUnavailable":"Камераны алдын ала көру қолжетімсіз", "settings.videoImportFailed":"Бейнені импорттау сәтсіз аяқталды", "settings.sourceSwitchBlocked":"Белсенді сеанс кезінде көзді ауыстыруға болмайды.",
    "metadata.teacher":"Мұғалім", "metadata.className":"Сынып / топ", "metadata.subject":"Пән", "metadata.notes":"Ескертпе (міндетті емес)",
    "metadata.confirm":"Бақылауды бастау", "metadata.forMode":"Сеанс түрі: {mode}", "metadata.proctor":"Мұғалім / бақылаушы", "metadata.classGroup":"Сынып / топ", "metadata.subjectExam":"Пән / емтихан", "metadata.startLesson":"Сабақты бастау", "metadata.startExam":"Емтиханды бастау", "detail.back":"← Сеанстарға оралу",
    "detail.overview":"Шолу", "detail.analytics":"Талдау", "detail.allTracks":"Барлық уақытша тректер",
    "detail.peopleOverTime":"Уақыт бойынша көрінген адамдар", "detail.byTrack":"Уақытша трек бойынша оқиғалар",
    "detail.occurrences":"Расталған оқиғалар саны; күйде өткізілген уақыт емес.",
    "detail.noDurations":"Күйдің аяқталу уақыты сақталмаған, сондықтан расталған ұзақтығын есептеу мүмкін емес.",
    "detail.noSamples":"Бұл сеанс үшін сақталған үлгілер жоқ.", "detail.seek":"Өту ↗",
    "detail.seekApprox":"Оқиғадан таймлапсқа өту шамамен жасалады; кадрлардың түсіп қалуы сәйкестікті өзгертуі мүмкін.",
    "detail.seekUnavailable":"Бұл ескі сеанс үшін уақыт бойынша өту қолжетімсіз."
  });
  Object.assign(translations.ru, {
    "settings.sourceManager":"Управление источником", "settings.cameraDevice":"Камера", "settings.noCameras":"Камеры не найдены", "settings.rescanCameras":"Повторить поиск камер", "settings.preview":"Предпросмотр", "settings.chooseVideo":"Выбрать видеофайл", "settings.dropVideo":"Перетащите видео сюда", "settings.videoReady":"Видео готово", "settings.duration":"Длительность", "settings.resolution":"Разрешение", "settings.frameRate":"Частота кадров", "settings.fileSize":"Размер файла", "settings.uploading":"Видео загружается…", "settings.endSessionSource":"Перед сменой источника завершите активную сессию.", "settings.cameraPreviewUnavailable":"Предпросмотр камеры недоступен", "settings.videoImportFailed":"Не удалось импортировать видео", "settings.sourceSwitchBlocked":"Во время активной сессии источник менять нельзя.",
    "metadata.teacher":"Учитель", "metadata.className":"Класс / группа", "metadata.subject":"Предмет", "metadata.notes":"Заметки (необязательно)",
    "metadata.confirm":"Начать наблюдение", "metadata.forMode":"Тип сессии: {mode}", "metadata.proctor":"Учитель / наблюдающий", "metadata.classGroup":"Класс / группа", "metadata.subjectExam":"Предмет / экзамен", "metadata.startLesson":"Начать урок", "metadata.startExam":"Начать экзамен", "detail.back":"← К сессиям",
    "detail.overview":"Обзор", "detail.analytics":"Аналитика", "detail.allTracks":"Все временные треки",
    "detail.peopleOverTime":"Люди в кадре по времени", "detail.byTrack":"События по временному треку",
    "detail.occurrences":"Число подтверждённых событий, а не время в состоянии.",
    "detail.noDurations":"Время окончания состояний не сохранялось, поэтому их подтверждённую длительность рассчитать нельзя.",
    "detail.noSamples":"Для этой сессии нет сохранённых отсчётов.", "detail.seek":"Перейти ↗",
    "detail.seekApprox":"Переход к событию в таймлапсе приблизителен: пропущенные кадры могут сместить соответствие.",
    "detail.seekUnavailable":"Для старой сессии нет данных времени для перехода."
  });
  const localeMap = { en: "en-US", kk: "kk-KZ", ru: "ru-RU" };
  Object.assign(translations.en, {'person.title':'People in this session','person.student':'Student','person.name':'Student #{id}','person.role':'Role','person.teacherExcluded':'Teacher observations are retained but excluded from student Exam statistics.','person.unknownExam':'Unknown observations','person.unknownNote':'Retained separately and not counted as student observations.',
    'person.first':'First seen','person.last':'Last seen','person.span':'Observed span','person.confirmed':'Confirmed events',
    'person.activity':'Session activity','person.find':'Find track ID','person.noMatches':'No matching tracks in this session.',
    'person.noBounds':'First and last observation times were not recorded for this older track.',
    'person.exam':'Exam observations','person.recentNote':'Most recent observations · confirmed occurrences',
    'person.previous':'← Previous','person.next':'Next →',
    'person.seekNote':'The recording does not store a frame-to-session time map. Use the player controls; event seeking is unavailable.'});
  Object.assign(translations.ru, {'person.title':'Люди в этой сессии','person.student':'Ученик','person.name':'Ученик #{id}','person.role':'Роль','person.teacherExcluded':'Наблюдения учителя сохраняются, но не входят в статистику экзамена для учеников.','person.unknownExam':'Неизвестные наблюдения','person.unknownNote':'Сохраняются отдельно и не считаются наблюдениями ученика.',
    'person.first':'Впервые замечен','person.last':'Последний раз замечен','person.span':'Период наблюдения','person.confirmed':'Подтверждённые события',
    'person.activity':'События сессии','person.find':'Найти номер трека','person.noMatches':'Подходящих треков в этой сессии нет.',
    'person.noBounds':'Для этого старого трека время первого и последнего наблюдения не сохранялось.',
    'person.exam':'Наблюдения на экзамене','person.recentNote':'Последние наблюдения · подтверждённые события',
    'person.previous':'← Назад','person.next':'Далее →',
    'person.seekNote':'В записи нет соответствия кадров времени сессии. Используйте управление плеером; переход по событию недоступен.'});
  Object.assign(translations.kk, {'person.title':'Осы сессиядағы адамдар','person.student':'Оқушы','person.name':'Оқушы #{id}','person.role':'Рөл','person.teacherExcluded':'Мұғалім бақылаулары сақталады, бірақ оқушы емтиханы статистикасына қосылмайды.','person.unknownExam':'Белгісіз бақылаулар','person.unknownNote':'Бөлек сақталады және оқушы бақылауы ретінде саналмайды.',
    'person.first':'Алғаш рет байқалды','person.last':'Соңғы рет байқалды','person.span':'Бақылау аралығы','person.confirmed':'Расталған оқиғалар',
    'person.activity':'Сессия оқиғалары','person.find':'Трек нөмірін іздеу','person.noMatches':'Бұл сессияда сәйкес тректер жоқ.',
    'person.noBounds':'Бұл бұрынғы тректің алғашқы және соңғы бақылау уақыты сақталмаған.',
    'person.exam':'Емтихандағы бақылаулар','person.recentNote':'Соңғы бақылаулар · расталған оқиғалар',
    'person.previous':'← Артқа','person.next':'Келесі →',
    'person.seekNote':'Жазбада кадрлардың сессия уақытына сәйкестігі сақталмаған. Плеерді пайдаланыңыз; оқиғаға өту қолжетімсіз.'});
  const phase2 = {
    en: { 'detail.people':'People','detail.recording':'Recording','detail.reviewEvidence':'Review evidence','detail.export':'Export session','detail.delete':'Delete session','detail.videoEvidence':'Video evidence','detail.reviewMoments':'Review moments · observable behavior','detail.first':'First seen','detail.last':'Last seen','detail.observed':'Observed span','detail.events':'Events','detail.review':'Review','detail.highReview':'High review','detail.timeline':'View timeline','detail.evidence':'View evidence','detail.noPeople':'No people found.','detail.noEvidence':'No evidence found for these filters.','detail.event':'Event','detail.duration':'Duration','detail.evidenceWindow':'Evidence window','detail.eventBegins':'Event begins at','detail.previous':'← Previous','detail.next':'Next →','detail.viewVideo':'View video','detail.loading':'Loading','detail.exporting':'Preparing export…','detail.exportReady':'Export ready.','detail.exportFailed':'Export failed','detail.deleteConfirm':'Delete this session? Your original imported video will NOT be deleted.','detail.originalSource':'Original source','detail.sessionRecording':'Session recording','detail.timelapse':'Timelapse','detail.evidenceClips':'Evidence clips','detail.filename':'Filename','detail.resolution':'Resolution','detail.fps':'FPS','detail.status':'Status','detail.source':'Source','detail.ready':'Ready','detail.unavailable':'Unavailable','detail.sampledTimelapse':'Sampled timelapse; intermediate motion was not recorded.','detail.noRecording':'No recording available.' },
    ru: { 'detail.people':'Люди','detail.recording':'Запись','detail.reviewEvidence':'Проверить материалы','detail.export':'Экспорт сессии','detail.delete':'Удалить сессию','detail.videoEvidence':'Видеоматериалы','detail.reviewMoments':'Моменты для проверки · наблюдаемое поведение','detail.first':'Впервые замечен','detail.last':'Последний раз замечен','detail.observed':'Период наблюдения','detail.events':'События','detail.review':'Проверка','detail.highReview':'Высокий приоритет','detail.timeline':'Открыть хронологию','detail.evidence':'Открыть материалы','detail.noPeople':'Люди не найдены.','detail.noEvidence':'По этим фильтрам материалы не найдены.','detail.event':'Событие','detail.duration':'Длительность','detail.evidenceWindow':'Окно материала','detail.eventBegins':'Событие начинается на','detail.previous':'← Назад','detail.next':'Далее →','detail.viewVideo':'Смотреть видео','detail.loading':'Загрузка','detail.exporting':'Подготовка экспорта…','detail.exportReady':'Экспорт готов.','detail.exportFailed':'Ошибка экспорта','detail.deleteConfirm':'Удалить эту сессию? Исходное импортированное видео НЕ будет удалено.','detail.originalSource':'Исходный источник','detail.sessionRecording':'Запись сессии','detail.timelapse':'Таймлапс','detail.evidenceClips':'Клипы материалов','detail.filename':'Имя файла','detail.resolution':'Разрешение','detail.fps':'FPS','detail.status':'Состояние','detail.source':'Источник','detail.ready':'Готово','detail.unavailable':'Недоступно','detail.sampledTimelapse':'Записан выборочный таймлапс; промежуточное движение не сохранено.','detail.noRecording':'Запись недоступна.' },
    kk: { 'detail.people':'Адамдар','detail.recording':'Жазба','detail.reviewEvidence':'Материалды қарау','detail.export':'Сессияны экспорттау','detail.delete':'Сессияны жою','detail.videoEvidence':'Бейне материалы','detail.reviewMoments':'Қаралатын сәттер · байқалатын әрекет','detail.first':'Алғаш рет байқалды','detail.last':'Соңғы рет байқалды','detail.observed':'Бақылау аралығы','detail.events':'Оқиғалар','detail.review':'Қарау','detail.highReview':'Жоғары басымдық','detail.timeline':'Хронологияны көру','detail.evidence':'Материалды көру','detail.noPeople':'Адамдар табылмады.','detail.noEvidence':'Бұл сүзгілер бойынша материал табылмады.','detail.event':'Оқиға','detail.duration':'Ұзақтығы','detail.evidenceWindow':'Материал аралығы','detail.eventBegins':'Оқиға басталатын орын','detail.previous':'← Алдыңғы','detail.next':'Келесі →','detail.viewVideo':'Бейнені көру','detail.loading':'Жүктелуде','detail.exporting':'Экспорт дайындалуда…','detail.exportReady':'Экспорт дайын.','detail.exportFailed':'Экспорт қатесі','detail.deleteConfirm':'Бұл сессия жойылсын ба? Түпнұсқа импортталған бейне ЖОЙЫЛМАЙДЫ.','detail.originalSource':'Түпнұсқа көз','detail.sessionRecording':'Сессия жазбасы','detail.timelapse':'Таймлапс','detail.evidenceClips':'Материал клиптері','detail.filename':'Файл атауы','detail.resolution':'Ажыратымдылық','detail.fps':'FPS','detail.status':'Күйі','detail.source':'Көз','detail.ready':'Дайын','detail.unavailable':'Қолжетімсіз','detail.sampledTimelapse':'Таңдамалы таймлапс жазылды; аралық қозғалыс сақталмады.','detail.noRecording':'Жазба қолжетімсіз.' }
  };
  Object.entries(phase2).forEach(([lang, values]) => Object.assign(translations[lang], values));
  Object.assign(translations.en, {'common.backendUnreachable':'Local NAZAR server is not reachable at {url}. Start serve.py (latest version) on this computer and allow local network access in the browser.'});
  Object.assign(translations.ru, {'common.backendUnreachable':'Локальный сервер NAZAR недоступен по адресу {url}. Запустите serve.py (последнюю версию) на этом компьютере и разрешите браузеру доступ к локальной сети.'});
  Object.assign(translations.kk, {'common.backendUnreachable':'NAZAR жергілікті сервері {url} мекенжайы бойынша қолжетімсіз. Осы компьютерде serve.py (соңғы нұсқасын) іске қосып, браузерге жергілікті желіге кіруге рұқсат беріңіз.'});
  let language = localStorage.getItem("nazar-language") || "en";
  if (!translations[language]) language = "en";

  function t(key, values) {
    const source = translations[language] || translations.en;
    let value = source[key] ?? translations.en[key] ?? key;
    Object.entries(values || {}).forEach(([name, replacement]) => {
      value = value.replaceAll(`{${name}}`, String(replacement));
    });
    return value;
  }

  function stateLabel(value) { return value ? t(`state.${value}`) : "—"; }
  function locale() { return localeMap[language] || "en-US"; }
  function getLanguage() { return language; }
  function setLanguage(next) {
    language = translations[next] ? next : "en";
    localStorage.setItem("nazar-language", language);
    document.documentElement.lang = language;
    applyI18n();
    document.dispatchEvent(new CustomEvent("nazar:languagechange", { detail: { language } }));
  }
  function applyI18n() {
    document.querySelectorAll("[data-i18n]").forEach((node) => {
      const value = t(node.dataset.i18n);
      if (node.children.length && node.firstChild && node.firstChild.nodeType === 3) node.firstChild.nodeValue = value;
      else node.textContent = value;
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
      node.placeholder = t(node.dataset.i18nPlaceholder);
    });
    document.querySelectorAll("[data-i18n-title]").forEach((node) => {
      node.title = t(node.dataset.i18nTitle);
    });
    document.querySelectorAll("[data-i18n-aria-label]").forEach((node) => {
      node.setAttribute("aria-label", t(node.dataset.i18nAriaLabel));
    });
    document.querySelectorAll("[data-i18n-alt]").forEach((node) => {
      node.setAttribute("alt", t(node.dataset.i18nAlt));
    });
    const languageSelect = document.querySelector("#language-select");
    if (languageSelect) languageSelect.value = language;
    const themeButton = document.querySelector("#theme-toggle");
    if (themeButton) themeButton.setAttribute("aria-label", t("nav.theme"));
    document.title = t("app.title");
  }
  function getTheme() { return localStorage.getItem("nazar-theme") || "light"; }
  function setTheme(next) {
    const theme = next === "dark" ? "dark" : "light";
    localStorage.setItem("nazar-theme", theme);
    document.documentElement.dataset.theme = theme;
    const button = document.querySelector("#theme-toggle");
    if (button) {
      button.dataset.theme = theme;
      button.textContent = theme === "dark" ? "☀" : "☾";
      button.setAttribute("title", t(theme === "dark" ? "theme.light" : "theme.dark"));
    }
    document.dispatchEvent(new CustomEvent("nazar:themechange", { detail: { theme } }));
  }
  window.NazarI18n = { translations, t, stateLabel, locale, getLanguage, setLanguage, applyI18n, getTheme, setTheme };
  document.documentElement.lang = language;
  document.documentElement.dataset.theme = getTheme();
  document.addEventListener("DOMContentLoaded", () => { applyI18n(); setTheme(getTheme()); });
})();
