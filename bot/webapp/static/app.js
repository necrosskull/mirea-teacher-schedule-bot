(function () {
  const tg = window.Telegram?.WebApp;
  if (tg) {
    tg.ready();
    tg.expand();
  }

  function haptic(type = 'light') {
    try {
      if (tg?.HapticFeedback) {
        tg.HapticFeedback.impactOccurred(type);
      }
    } catch (e) {
      // Ignore if not supported
    }
  }

  const DAY_NAMES = ['ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ', 'СБ'];
  const MONTH_NAMES = [
    'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
    'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
  ];

  // Application State
  const state = {
    user: null,
    currentEntity: null,
    isFavorite: false,
    selectedWeek: 1,
    currentWeek: 1,
    selectedDay: 1, // 1=Mon, 6=Sat
    weekDays: {}, // map 1..6 -> { date, weekday, lessons: [] }
    datesSummary: {}, // map 'YYYY-MM-DD' -> ['lecture', 'practice', ...]
    activeFilter: 'all', // 'all' | 'lecture' | 'practice' | 'lab'
    initData: tg?.initData || '',
    calYear: new Date().getFullYear(),
    calMonth: new Date().getMonth(), // 0..11
  };

  // DOM Elements
  const entityTitleEl = document.getElementById('entityTitle');
  const entitySubtitleEl = document.getElementById('entitySubtitle');
  const btnFavEl = document.getElementById('btnFav');
  const starIconEl = document.getElementById('starIcon');
  const btnSearchEl = document.getElementById('btnSearch');
  const btnCalendarEl = document.getElementById('btnCalendar');
  const prevWeekBtn = document.getElementById('prevWeek');
  const nextWeekBtn = document.getElementById('nextWeek');
  const weekLabelEl = document.getElementById('weekLabel');
  const parityLabelEl = document.getElementById('parityLabel');
  const weekInfoContainer = document.getElementById('weekInfoContainer');
  const btnTodayEl = document.getElementById('btnToday');
  const dayRibbonEl = document.getElementById('dayRibbon');
  const scheduleSliderEl = document.getElementById('scheduleSlider');
  const swipeAreaEl = document.getElementById('swipeArea');
  const liveDayWidgetEl = document.getElementById('liveDayWidget');

  // Search Modal

  const searchModalEl = document.getElementById('searchModal');
  const searchOverlayEl = document.getElementById('searchOverlay');
  const searchInputEl = document.getElementById('searchInput');
  const searchResultsEl = document.getElementById('searchResults');
  const closeSearchBtn = document.getElementById('closeSearch');

  // Calendar Modal
  const calendarModalEl = document.getElementById('calendarModal');
  const calendarOverlayEl = document.getElementById('calendarOverlay');
  const calMonthLabelEl = document.getElementById('calMonthLabel');
  const calPrevMonthBtn = document.getElementById('calPrevMonth');
  const calNextMonthBtn = document.getElementById('calNextMonth');
  const calendarGridEl = document.getElementById('calendarGrid');
  const calBtnTodayEl = document.getElementById('calBtnToday');
  const calBtnCloseEl = document.getElementById('calBtnClose');

  // Admin Modal
  const btnAdminEl = document.getElementById('btnAdmin');
  const adminModalEl = document.getElementById('adminModal');
  const adminBtnCloseEl = document.getElementById('adminBtnClose');
  const tabBtnStats = document.getElementById('tabBtnStats');
  const tabBtnMaintenance = document.getElementById('tabBtnMaintenance');
  const tabBtnBroadcast = document.getElementById('tabBtnBroadcast');
  const adminViewStats = document.getElementById('adminViewStats');
  const adminViewMaintenance = document.getElementById('adminViewMaintenance');
  const adminViewBroadcast = document.getElementById('adminViewBroadcast');
  const statTotalUsersEl = document.getElementById('statTotalUsers');
  const statFavUsersEl = document.getElementById('statFavUsers');
  const statNotifyUsersEl = document.getElementById('statNotifyUsers');
  const topGroupsListEl = document.getElementById('topGroupsList');
  const topTeachersListEl = document.getElementById('topTeachersList');
  const topClassroomsListEl = document.getElementById('topClassroomsList');
  const maintSwitchEl = document.getElementById('maintSwitch');
  const maintMessageInputEl = document.getElementById('maintMessageInput');
  const btnSaveMaintenanceEl = document.getElementById('btnSaveMaintenance');
  const maintAlertEl = document.getElementById('maintAlert');
  const bcTextInputEl = document.getElementById('bcTextInput');
  const bcFileInputEl = document.getElementById('bcFileInput');
  const bcUploadStatusEl = document.getElementById('bcUploadStatus');
  const bcMediaUrlInputEl = document.getElementById('bcMediaUrlInput');
  const bcBtnTextInputEl = document.getElementById('bcBtnTextInput');
  const bcBtnUrlInputEl = document.getElementById('bcBtnUrlInput');
  const tgPreviewMediaEl = document.getElementById('tgPreviewMedia');
  const tgPreviewTextEl = document.getElementById('tgPreviewText');
  const tgPreviewTimeEl = document.getElementById('tgPreviewTime');
  const tgPreviewBtnWrapperEl = document.getElementById('tgPreviewBtnWrapper');
  const tgPreviewBtnTextEl = document.getElementById('tgPreviewBtnText');
  const btnBcTestEl = document.getElementById('btnBcTest');
  const btnBcSendAllEl = document.getElementById('btnBcSendAll');
  const bcAlertEl = document.getElementById('bcAlert');


  const toastEl = document.getElementById('toast');


  function showToast(text) {
    toastEl.textContent = text;
    toastEl.classList.remove('hidden');
    setTimeout(() => {
      toastEl.classList.add('hidden');
    }, 2500);
  }

  // Swipe Gesture Handling
  let touchStartX = 0;
  let touchStartY = 0;
  let touchEndX = 0;
  let touchEndY = 0;

  swipeAreaEl.addEventListener(
    'touchstart',
    (e) => {
      touchStartX = e.changedTouches[0].screenX;
      touchStartY = e.changedTouches[0].screenY;
    },
    { passive: true }
  );

  swipeAreaEl.addEventListener(
    'touchend',
    (e) => {
      touchEndX = e.changedTouches[0].screenX;
      touchEndY = e.changedTouches[0].screenY;
      handleSwipeGesture();
    },
    { passive: true }
  );

  function handleSwipeGesture() {
    const deltaX = touchEndX - touchStartX;
    const deltaY = touchEndY - touchStartY;

    if (Math.abs(deltaX) > 45 && Math.abs(deltaX) > Math.abs(deltaY) * 1.4) {
      if (deltaX < 0) {
        // Swipe Left -> Next Day
        if (state.selectedDay < 6) {
          switchDay(state.selectedDay + 1, 'left');
        } else if (state.selectedWeek < 24) {
          // Transition to Monday of next week
          haptic('medium');
          loadSchedule(state.currentEntity, state.selectedWeek + 1, null, 1, 'left');
          showToast(`Неделя ${state.selectedWeek + 1}`);
        }
      } else {
        // Swipe Right -> Previous Day
        if (state.selectedDay > 1) {
          switchDay(state.selectedDay - 1, 'right');
        } else if (state.selectedWeek > 1) {
          // Transition to Saturday of previous week
          haptic('medium');
          loadSchedule(state.currentEntity, state.selectedWeek - 1, null, 6, 'right');
          showToast(`Неделя ${state.selectedWeek - 1}`);
        }
      }
    }
  }

  function switchDay(dayIndex, direction = 'left') {
    haptic('light');
    state.selectedDay = dayIndex;
    renderDayRibbon();
    renderLessons(direction);
  }

  function getLocalDateISO(d = new Date()) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  }

  function getLessonTimes(startTimeStr, endTimeStr) {
    const now = new Date();
    const [sh, sm] = (startTimeStr || '00:00').split(':').map(Number);
    const [eh, em] = (endTimeStr || '00:00').split(':').map(Number);

    const start = new Date(now);
    start.setHours(sh, sm, 0, 0);

    const end = new Date(now);
    end.setHours(eh, em, 0, 0);

    return { start, end, now };
  }

  function isLessonNow(startTimeStr, endTimeStr, lessonDateStr) {
    try {
      const now = new Date();
      const todayISO = getLocalDateISO(now);
      if (lessonDateStr && lessonDateStr !== todayISO) return false;

      const { start, end } = getLessonTimes(startTimeStr, endTimeStr);
      return now >= start && now <= end;
    } catch (e) {
      return false;
    }
  }


  function getRemainingMinutes(endTimeStr) {
    try {
      const { end, now } = getLessonTimes('00:00', endTimeStr);
      const diffMs = end - now;
      return Math.max(1, Math.round(diffMs / 60000));
    } catch (e) {
      return 0;
    }
  }

  function getMinutesUntilStart(startTimeStr) {
    try {
      const { start, now } = getLessonTimes(startTimeStr, '23:59');
      const diffMs = start - now;
      return Math.round(diffMs / 60000);
    } catch (e) {
      return -1;
    }
  }

  function getTypeBadgeClass(type) {
    const t = (type || '').toLowerCase();
    if (t.includes('лекц') || t.includes('lecture')) return 'type-lecture';
    if (t.includes('практ') || t.includes('practice')) return 'type-practice';
    if (t.includes('лаб') || t.includes('laboratory')) return 'type-lab';
    if (t.includes('экзамен') || t.includes('exam') || t.includes('зачет')) return 'type-exam';
    return 'type-default';
  }

  function getDotClass(type) {
    const t = (type || '').toLowerCase();
    if (t.includes('лекц') || t.includes('lecture')) return 'dot-lecture';
    if (t.includes('практ') || t.includes('practice')) return 'dot-practice';
    if (t.includes('лаб') || t.includes('laboratory')) return 'dot-lab';
    if (t.includes('экзамен') || t.includes('exam') || t.includes('зачет')) return 'dot-exam';
    return 'dot-other';
  }

  function getTypeDisplayName(type) {
    const t = (type || '').toLowerCase();
    if (t.includes('лекц') || t.includes('lecture')) return 'Лекция';
    if (t.includes('практ') || t.includes('practice')) return 'Практика';
    if (t.includes('лаб') || t.includes('laboratory')) return 'Лабораторная';
    if (t.includes('экзамен') || t.includes('exam')) return 'Экзамен';
    if (t.includes('зачет') || t.includes('credit')) return 'Зачёт';
    return type || 'Занятие';
  }

  function renderDayRibbon() {
    dayRibbonEl.innerHTML = '';
    for (let day = 1; day <= 6; day++) {
      const dayData = state.weekDays[day] || { lessons: [] };
      const hasLessons = dayData.lessons && dayData.lessons.length > 0;
      const isActive = day === state.selectedDay;

      let dateStr = '';
      if (dayData.date) {
        const parts = dayData.date.split('-');
        if (parts.length === 3) dateStr = `${parts[2]}.${parts[1]}`;
      }

      const tab = document.createElement('div');
      tab.className = `day-tab ${isActive ? 'active' : ''} ${hasLessons ? 'has-lessons' : ''}`;
      tab.innerHTML = `
        <span class="day-tab-title">${DAY_NAMES[day - 1]}</span>
        <span class="day-tab-date">${dateStr}</span>
        <span class="day-tab-dot"></span>
      `;

      tab.addEventListener('click', () => {
        if (state.selectedDay !== day) {
          const dir = day > state.selectedDay ? 'left' : 'right';
          switchDay(day, dir);
        }
      });

      dayRibbonEl.appendChild(tab);
    }
  }

  function updateLiveDayWidget(rawLessons, currentDateStr) {
    const todayISO = getLocalDateISO();
    if (currentDateStr !== todayISO || !rawLessons || rawLessons.length === 0) {

      liveDayWidgetEl.classList.add('hidden');
      return;
    }

    const now = new Date();
    let currentLesson = null;
    let nextLesson = null;
    let lastPastLesson = null;
    let progressPercent = 0;
    let remainingMins = 0;
    let minsUntilNext = 0;

    for (const l of rawLessons) {
      const { start, end } = getLessonTimes(l.start_time, l.end_time);
      if (now >= start && now <= end) {
        currentLesson = l;
        const totalMs = end - start;
        const elapsedMs = now - start;
        progressPercent = Math.min(100, Math.max(0, Math.round((elapsedMs / totalMs) * 100)));
        remainingMins = Math.max(1, Math.round((end - now) / 60000));
      } else if (now < start) {
        if (!nextLesson) {
          nextLesson = l;
          minsUntilNext = Math.max(1, Math.round((start - now) / 60000));
        }
      } else if (now > end) {
        lastPastLesson = l;
      }
    }

    liveDayWidgetEl.classList.remove('hidden');

    // State 1: A lesson is currently underway!
    if (currentLesson) {
      const existingCurrent = liveDayWidgetEl.querySelector('.live-widget.current-state');
      if (existingCurrent) {
        const countdownEl = existingCurrent.querySelector('.live-countdown');
        const expectedCountdown = `⏳ Осталось ${remainingMins} мин`;
        if (countdownEl && countdownEl.textContent !== expectedCountdown) {
          countdownEl.textContent = expectedCountdown;
        }
        const fillEl = existingCurrent.querySelector('.live-progress-fill');
        if (fillEl) fillEl.style.width = `${progressPercent}%`;
        return;
      }

      const room = currentLesson.classrooms && currentLesson.classrooms[0] ? `🏫 ${currentLesson.classrooms[0]}` : '';
      const teacher = currentLesson.teachers && currentLesson.teachers[0] ? `👨🏻‍🏫 ${currentLesson.teachers[0]}` : '';
      const nextSnippet = nextLesson
        ? `<div class="live-widget-next">
             <span class="live-next-tag">СЛЕДУЮЩАЯ:</span>
             <span class="live-next-text">${nextLesson.number} пара (${nextLesson.start_time}) • ${nextLesson.subject}</span>
           </div>`
        : '';

      liveDayWidgetEl.innerHTML = `
        <div class="live-widget current-state" id="activeLiveCard">
          <div class="live-widget-top">
            <div class="live-pill live-pill-green">
              <span class="pulse-dot"></span>
              <span>ИДЁТ ${currentLesson.number} ПАРА</span>
            </div>
            <span class="live-countdown">⏳ Осталось ${remainingMins} мин</span>
          </div>
          <div class="live-subject">${currentLesson.subject}</div>
          <div class="live-meta">
            ${room ? `<span>${room}</span>` : ''}
            ${teacher ? `<span>${teacher}</span>` : ''}
          </div>
          <div class="live-progress-bar">
            <div class="live-progress-fill" style="width: ${progressPercent}%"></div>
          </div>
          ${nextSnippet}
        </div>
      `;
    }
    // State 2: Break between classes (Перемена!)
    else if (nextLesson && lastPastLesson) {
      const existingBreak = liveDayWidgetEl.querySelector('.live-widget.break-state');
      if (existingBreak) {
        const countdownEl = existingBreak.querySelector('.live-countdown');
        const expectedCountdown = `До звонка ${minsUntilNext} мин`;
        if (countdownEl && countdownEl.textContent !== expectedCountdown) {
          countdownEl.textContent = expectedCountdown;
        }
        return;
      }

      const room = nextLesson.classrooms && nextLesson.classrooms[0] ? `🏫 ${nextLesson.classrooms[0]}` : '';
      const teacher = nextLesson.teachers && nextLesson.teachers[0] ? `👨🏻‍🏫 ${nextLesson.teachers[0]}` : '';

      liveDayWidgetEl.innerHTML = `
        <div class="live-widget break-state" id="activeLiveCard">
          <div class="live-widget-top">
            <div class="live-pill live-pill-orange">
              <span>☕</span>
              <span>ПЕРЕМЕНА</span>
            </div>
            <span class="live-countdown">До звонка ${minsUntilNext} мин</span>
          </div>
          <div class="live-subtitle">Следующая пара (${nextLesson.start_time}):</div>
          <div class="live-subject">${nextLesson.number} пара • ${nextLesson.subject}</div>
          <div class="live-meta">
            ${room ? `<span>${room}</span>` : ''}
            ${teacher ? `<span>${teacher}</span>` : ''}
          </div>
        </div>
      `;
    }
    // State 3: Before first lesson today
    else if (nextLesson && !lastPastLesson) {
      const timeFmt =
        minsUntilNext > 60
          ? `${Math.floor(minsUntilNext / 60)} ч ${minsUntilNext % 60} мин`
          : `${minsUntilNext} мин`;

      const existingBefore = liveDayWidgetEl.querySelector('.live-widget.before-state');
      if (existingBefore) {
        const countdownEl = existingBefore.querySelector('.live-countdown');
        const expectedCountdown = `Через ${timeFmt}`;
        if (countdownEl && countdownEl.textContent !== expectedCountdown) {
          countdownEl.textContent = expectedCountdown;
        }
        return;
      }

      const room = nextLesson.classrooms && nextLesson.classrooms[0] ? `🏫 ${nextLesson.classrooms[0]}` : '';

      liveDayWidgetEl.innerHTML = `
        <div class="live-widget before-state" id="activeLiveCard">
          <div class="live-widget-top">
            <div class="live-pill live-pill-blue">
              <span>🌅</span>
              <span>СКОРО НАЧАЛО</span>
            </div>
            <span class="live-countdown">Через ${timeFmt}</span>
          </div>
          <div class="live-subtitle">1-я пара в ${nextLesson.start_time}:</div>
          <div class="live-subject">${nextLesson.number} пара • ${nextLesson.subject}</div>
          <div class="live-meta">
            ${room ? `<span>${room}</span>` : ''}
          </div>
        </div>
      `;
    }
    // State 4: All lessons finished for today
    else if (!currentLesson && !nextLesson && rawLessons.length > 0) {
      const existingDone = liveDayWidgetEl.querySelector('.live-widget.done-state');
      if (existingDone) return;

      liveDayWidgetEl.innerHTML = `
        <div class="live-widget done-state">
          <div class="live-widget-top">
            <div class="live-pill live-pill-purple">
              <span>🎉</span>
              <span>ДЕНЬ ЗАВЕРШЁН</span>
            </div>
          </div>
          <div class="live-subject">Все пары на сегодня закончились!</div>
          <div class="live-meta">
            <span>Проведено пар: ${rawLessons.length}. Отличного отдыха ✨</span>
          </div>
        </div>
      `;
    }


    const card = document.getElementById('activeLiveCard');
    if (card) {
      card.addEventListener('click', () => {
        haptic('light');
        const target =
          document.querySelector('.active-lesson') ||
          document.querySelector('.next-lesson-card');
        if (target) {
          target.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      });
    }
  }

  function renderLessons(slideDirection = null) {
    scheduleSliderEl.innerHTML = '';
    if (slideDirection === 'left') {
      scheduleSliderEl.className = 'schedule-slider slide-left';
    } else if (slideDirection === 'right') {
      scheduleSliderEl.className = 'schedule-slider slide-right';
    } else {
      scheduleSliderEl.className = 'schedule-slider';
    }

    const currentDayData = state.weekDays[state.selectedDay];
    const rawLessons = currentDayData?.lessons || [];

    updateLiveDayWidget(rawLessons, currentDayData?.date);

    // Apply Filter
    let lessons = rawLessons;
    if (state.activeFilter !== 'all') {
      lessons = rawLessons.filter((l) => {
        const t = (l.lesson_type || '').toLowerCase();
        if (state.activeFilter === 'lecture') return t.includes('лекц') || t.includes('lecture');
        if (state.activeFilter === 'practice') return t.includes('практ') || t.includes('practice');
        if (state.activeFilter === 'lab') return t.includes('лаб') || t.includes('laboratory');
        return true;
      });
    }

    if (lessons.length === 0) {
      const subtitle =
        rawLessons.length > 0
          ? 'По выбранному фильтру занятий не найдено.'
          : 'В этот день занятий не запланировано. Отличный повод отдохнуть!';
      scheduleSliderEl.innerHTML = `
        <div class="empty-day-state">
          <div class="empty-day-icon">🏖️</div>
          <div class="empty-day-title">${rawLessons.length > 0 ? 'Нет пар по фильтру' : 'Пар нет!'}</div>
          <div class="empty-day-subtitle">${subtitle}</div>
        </div>
      `;
      return;
    }

    const now = new Date();
    const todayISO = getLocalDateISO(now);
    const isToday = currentDayData?.date === todayISO;


    // Find current and next lesson among rawLessons
    let currentLessonObj = null;
    let nextLessonObj = null;
    let curProgress = 0;
    let curRemaining = 0;

    if (isToday) {
      for (const l of rawLessons) {
        const { start, end } = getLessonTimes(l.start_time, l.end_time);
        if (now >= start && now <= end) {
          currentLessonObj = l;
          const totalMs = end - start;
          const elapsedMs = now - start;
          curProgress = Math.min(100, Math.max(0, Math.round((elapsedMs / totalMs) * 100)));
          curRemaining = Math.max(1, Math.round((end - now) / 60000));
        } else if (now < start && !nextLessonObj) {
          nextLessonObj = l;
        }
      }
    }

    lessons.forEach((lesson) => {
      let cardClass = 'lesson-card';
      let statusBadge = '';
      let progressLineHtml = '';

      if (isToday) {
        const { start, end } = getLessonTimes(lesson.start_time, lesson.end_time);
        const isNow = lesson === currentLessonObj;
        const isNext = lesson === nextLessonObj;
        const isPast = now > end;

        if (isNow) {
          cardClass += ' active-lesson';
          progressLineHtml = `<div class="card-live-progress" style="width: ${curProgress}%"></div>`;
          statusBadge = `<span class="now-badge"><span class="pulse-dot"></span>Идет (${curRemaining} мин)</span>`;
        } else if (isNext) {
          cardClass += ' next-lesson-card';
          const minsUntil = Math.max(1, Math.round((start - now) / 60000));
          statusBadge = `<span class="next-badge">⏱️ Следующая (${minsUntil} мин)</span>`;
        } else if (isPast) {
          cardClass += ' past-lesson-card';
          statusBadge = `<span class="past-badge">✓ Прошла</span>`;
        }
      }

      if (!statusBadge) {
        const badgeClass = getTypeBadgeClass(lesson.lesson_type);
        const typeName = getTypeDisplayName(lesson.lesson_type);
        statusBadge = `<span class="lesson-type-badge ${badgeClass}">${typeName}</span>`;
      }

      const card = document.createElement('div');
      card.className = cardClass;

      let detailsHtml = '';
      if (lesson.teachers && lesson.teachers.length > 0) {
        detailsHtml += `
          <div class="detail-item">
            <span class="detail-icon">👨🏻‍🏫</span>
            <span>${lesson.teachers.join(', ')}</span>
          </div>
        `;
      }
      if (lesson.classrooms && lesson.classrooms.length > 0) {
        detailsHtml += `
          <div class="detail-item">
            <span class="detail-icon">🏫</span>
            <span>${lesson.classrooms.join(', ')}</span>
          </div>
        `;
      }
      if (lesson.groups && lesson.groups.length > 0) {
        detailsHtml += `
          <div class="detail-item">
            <span class="detail-icon">👥</span>
            <span>${lesson.groups.join(', ')}</span>
          </div>
        `;
      }

      card.innerHTML = `
        ${progressLineHtml}
        <div class="lesson-card-header">
          <div class="lesson-time-wrap">
            <span class="lesson-number">${lesson.number}</span>
            <span class="lesson-time">${lesson.start_time} – ${lesson.end_time}</span>
          </div>
          ${statusBadge}
        </div>
        <div class="lesson-subject">${lesson.subject}</div>
        <div class="lesson-details">${detailsHtml}</div>
      `;

      scheduleSliderEl.appendChild(card);
    });
  }


  function updateHeader() {
    if (!state.currentEntity) return;

    entityTitleEl.textContent = state.currentEntity.name;
    if (entitySubtitleEl) {
      const typeRu =
        state.currentEntity.type === 'teacher'
          ? 'Преподаватель'
          : state.currentEntity.type === 'classroom'
          ? 'Аудитория'
          : 'Группа';
      entitySubtitleEl.textContent = typeRu;
    }


    const isFav =
      state.user &&
      state.user.favorite &&
      state.user.favorite.trim().toLowerCase() ===
        state.currentEntity.name.trim().toLowerCase();
    state.isFavorite = Boolean(isFav);

    if (state.isFavorite) {
      starIconEl.classList.add('star-active');
    } else {
      starIconEl.classList.remove('star-active');
    }
  }

  function updateWeekBar() {
    weekLabelEl.textContent = `Неделя ${state.selectedWeek}`;
    parityLabelEl.textContent = state.selectedWeek % 2 === 0 ? 'Чётная' : 'Нечётная';
  }

  async function loadSchedule(entity, week = null, targetDate = null, targetDay = null, slideDirection = null) {
    const targetWeek = week || state.selectedWeek;
    state.currentEntity = entity;
    updateHeader();

    if (targetDay !== null) {
      state.selectedDay = targetDay;
    }

    try {
      const params = {
        type: entity.type,
        uid: entity.uid,
        name: entity.name,
        init_data: state.initData,
      };
      if (targetDate) {
        params.date = targetDate;
      } else {
        params.week = targetWeek;
      }

      const query = new URLSearchParams(params);
      const res = await fetch(`/api/schedule?${query.toString()}`, {
        headers: { 'X-Telegram-Init-Data': state.initData },
      });

      if (!res.ok) throw new Error('Ошибка сети');

      const data = await res.json();
      state.weekDays = data.days || {};
      state.datesSummary = data.dates_summary || state.datesSummary || {};
      state.selectedWeek = data.week || targetWeek;
      state.currentWeek = data.current_week || 1;

      if (data.target_weekday && targetDay === null) {
        state.selectedDay = Math.min(6, Math.max(1, data.target_weekday));
      } else if (targetDay === null && !targetDate) {
        if (state.selectedWeek === state.currentWeek) {
          const todayWd = new Date().getDay();
          state.selectedDay = todayWd === 0 ? 1 : todayWd;
        } else {
          state.selectedDay = 1;
        }
      }


      try {
        localStorage.setItem(
          'cached_fav_schedule',
          JSON.stringify({
            entity: state.currentEntity,
            days: state.weekDays,
            week: state.selectedWeek,
            datesSummary: state.datesSummary,
          })
        );
      } catch (e) {}

      updateWeekBar();
      renderDayRibbon();
      renderLessons(slideDirection);
    } catch (err) {
      showToast('Не удалось загрузить расписание');
    }
  }

  // Interactive Month Calendar Logic
  function openCalendar() {
    haptic('medium');
    calendarModalEl.classList.remove('hidden');

    // Default view to currently selected week date
    const curDay = state.weekDays[state.selectedDay];
    if (curDay && curDay.date) {
      const parts = curDay.date.split('-').map(Number);
      state.calYear = parts[0];
      state.calMonth = parts[1] - 1;
    } else {
      const now = new Date();
      state.calYear = now.getFullYear();
      state.calMonth = now.getMonth();
    }

    renderCalendarGrid();
  }

  function closeCalendar() {
    calendarModalEl.classList.add('hidden');
  }

  function getSemesterWeekForDate(d) {
    const y = d.getFullYear();
    const m = d.getMonth() + 1;
    let semStart;
    if (m >= 8) {
      semStart = new Date(y, 8, 1);
    } else if (m < 2) {
      semStart = new Date(y - 1, 8, 1);
    } else {
      semStart = new Date(y, 1, 9);
    }
    if (semStart.getDay() === 0) semStart.setDate(semStart.getDate() + 1);

    const diffDays = Math.floor((d - semStart) / (1000 * 60 * 60 * 24));
    if (diffDays < 0) return 1;
    return Math.max(1, Math.min(24, Math.floor(diffDays / 7) + 1));
  }

  function prevMonth() {
    haptic('light');
    state.calMonth--;
    if (state.calMonth < 0) {
      state.calMonth = 11;
      state.calYear--;
    }
    renderCalendarGrid('right');
  }

  function nextMonth() {
    haptic('light');
    state.calMonth++;
    if (state.calMonth > 11) {
      state.calMonth = 0;
      state.calYear++;
    }
    renderCalendarGrid('left');
  }

  function renderCalendarGrid(direction = null) {
    calMonthLabelEl.textContent = `${MONTH_NAMES[state.calMonth]} ${state.calYear}`;
    calendarGridEl.innerHTML = '';

    if (direction === 'left') {
      calendarGridEl.className = 'calendar-grid cal-slide-left';
    } else if (direction === 'right') {
      calendarGridEl.className = 'calendar-grid cal-slide-right';
    } else {
      calendarGridEl.className = 'calendar-grid';
    }

    const firstDayOfMonth = new Date(state.calYear, state.calMonth, 1);
    const lastDayOfMonth = new Date(state.calYear, state.calMonth + 1, 0);

    // Monday is 1, Sunday is 7
    let startWd = firstDayOfMonth.getDay();
    if (startWd === 0) startWd = 7;

    const startDate = new Date(firstDayOfMonth);
    startDate.setDate(firstDayOfMonth.getDate() - (startWd - 1));

    const todayISO = getLocalDateISO();
    const curActiveDate = state.weekDays[state.selectedDay]?.date;


    let rowDate = new Date(startDate);

    // Render 5 or 6 weeks
    for (let w = 0; w < 6; w++) {
      if (w > 0 && rowDate.getMonth() !== state.calMonth && rowDate > lastDayOfMonth) {
        break;
      }

      const rowEl = document.createElement('div');
      rowEl.className = 'cal-row';

      // Week Number Column
      const semWk = getSemesterWeekForDate(rowDate);
      const wkCell = document.createElement('div');
      wkCell.className = 'cal-wk-cell';
      wkCell.textContent = semWk;
      rowEl.appendChild(wkCell);

      for (let day = 0; day < 7; day++) {
        const cellDate = new Date(rowDate);
        const y = cellDate.getFullYear();
        const m = String(cellDate.getMonth() + 1).padStart(2, '0');
        const d = String(cellDate.getDate()).padStart(2, '0');
        const iso = `${y}-${m}-${d}`;

        const isCurrentMonth = cellDate.getMonth() === state.calMonth;
        const isToday = iso === todayISO;
        const isActive = iso === curActiveDate;

        const cell = document.createElement('div');
        cell.className = `cal-day-cell ${!isCurrentMonth ? 'other-month' : ''} ${isToday ? 'today-cal-day' : ''} ${isActive ? 'active-cal-day' : ''}`;

        // Colored Dots
        let dotsHtml = '';
        const dayTypes = state.datesSummary[iso];
        if (dayTypes && dayTypes.length > 0) {
          const uniqueTypes = [...new Set(dayTypes)].slice(0, 4);
          const dots = uniqueTypes
            .map((t) => `<span class="cal-dot ${getDotClass(t)}"></span>`)
            .join('');
          dotsHtml = `<div class="cal-dots">${dots}</div>`;
        }

        cell.innerHTML = `
          <span class="cal-date-num">${cellDate.getDate()}</span>
          ${dotsHtml}
        `;

        cell.addEventListener('click', () => {
          haptic('medium');
          closeCalendar();
          loadSchedule(state.currentEntity, null, iso);
        });

        rowEl.appendChild(cell);
        rowDate.setDate(rowDate.getDate() + 1);
      }

      calendarGridEl.appendChild(rowEl);
    }
  }

  // Calendar Swipe Gestures
  let calTouchStartX = 0;
  let calTouchStartY = 0;
  let calTouchEndX = 0;
  let calTouchEndY = 0;

  calendarGridEl.addEventListener(
    'touchstart',
    (e) => {
      calTouchStartX = e.changedTouches[0].screenX;
      calTouchStartY = e.changedTouches[0].screenY;
    },
    { passive: true }
  );

  calendarGridEl.addEventListener(
    'touchend',
    (e) => {
      calTouchEndX = e.changedTouches[0].screenX;
      calTouchEndY = e.changedTouches[0].screenY;
      const deltaX = calTouchEndX - calTouchStartX;
      const deltaY = calTouchEndY - calTouchStartY;

      if (Math.abs(deltaX) > 40 && Math.abs(deltaX) > Math.abs(deltaY) * 1.3) {
        if (deltaX < 0) {
          // Swipe Left -> Next Month
          nextMonth();
        } else {
          // Swipe Right -> Previous Month
          prevMonth();
        }
      }
    },
    { passive: true }
  );

  // Filter Pills Handling
  document.querySelectorAll('.filter-pill').forEach((pill) => {
    pill.addEventListener('click', (e) => {
      haptic('light');
      document.querySelectorAll('.filter-pill').forEach((p) => p.classList.remove('active'));
      pill.classList.add('active');
      state.activeFilter = pill.dataset.filter;
      renderLessons();
    });
  });

  // Calendar Event Listeners
  btnCalendarEl.addEventListener('click', openCalendar);
  weekInfoContainer.addEventListener('click', openCalendar);
  calendarOverlayEl.addEventListener('click', closeCalendar);
  calBtnCloseEl.addEventListener('click', closeCalendar);

  calPrevMonthBtn.addEventListener('click', prevMonth);
  calNextMonthBtn.addEventListener('click', nextMonth);


  calBtnTodayEl.addEventListener('click', () => {
    haptic('medium');
    closeCalendar();
    const todayISO = getLocalDateISO();
    const todayWd = new Date().getDay();
    state.selectedDay = todayWd === 0 ? 1 : todayWd;
    loadSchedule(state.currentEntity, null, todayISO);
  });

  // Week Arrows
  prevWeekBtn.addEventListener('click', () => {
    if (state.selectedWeek > 1) {
      haptic('light');
      loadSchedule(state.currentEntity, state.selectedWeek - 1);
    }
  });

  nextWeekBtn.addEventListener('click', () => {
    if (state.selectedWeek < 24) {
      haptic('light');
      loadSchedule(state.currentEntity, state.selectedWeek + 1);
    }
  });

  btnTodayEl.addEventListener('click', () => {
    haptic('medium');
    const todayWd = new Date().getDay();
    state.selectedDay = todayWd === 0 ? 1 : todayWd;
    const todayISO = getLocalDateISO();
    loadSchedule(state.currentEntity, null, todayISO);
  });


  // Favorite Star Toggle
  btnFavEl.addEventListener('click', async () => {
    if (!state.currentEntity) return;
    haptic('medium');

    const newFav = state.isFavorite ? '' : state.currentEntity.name;
    try {
      const res = await fetch(`/api/me/favorite?init_data=${encodeURIComponent(state.initData)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ favorite: newFav }),
      });

      if (res.ok) {
        if (!state.user) state.user = {};
        state.user.favorite = newFav;
        state.isFavorite = Boolean(newFav);
        updateHeader();
        showToast(state.isFavorite ? '⭐ Сохранено в избранное' : 'Удалено из избранного');
      }
    } catch (e) {
      showToast('Ошибка сохранения избранного');
    }
  });

  // Search Logic
  function openSearch() {
    haptic('light');
    searchModalEl.classList.remove('hidden');
    searchInputEl.value = '';
    searchInputEl.focus();
  }

  function closeSearch() {
    searchModalEl.classList.add('hidden');
  }

  btnSearchEl.addEventListener('click', openSearch);
  closeSearchBtn.addEventListener('click', closeSearch);
  searchOverlayEl.addEventListener('click', closeSearch);

  let searchTimeout = null;
  searchInputEl.addEventListener('input', (e) => {
    clearTimeout(searchTimeout);
    const query = e.target.value.trim();
    if (query.length < 2) {
      searchResultsEl.innerHTML = `<div class="search-placeholder">Начните вводить название группы, преподавателя или аудиторию...</div>`;
      return;
    }

    searchTimeout = setTimeout(async () => {
      try {
        const res = await fetch(
          `/api/search?q=${encodeURIComponent(query)}&init_data=${encodeURIComponent(state.initData)}`,
          { headers: { 'X-Telegram-Init-Data': state.initData } }
        );
        if (!res.ok) throw new Error();

        const items = await res.json();

        if (!items || items.length === 0) {
          searchResultsEl.innerHTML = `<div class="search-placeholder">Ничего не найдено по запросу «${query}»</div>`;
          return;
        }

        searchResultsEl.innerHTML = '';
        items.forEach((item) => {
          const div = document.createElement('div');
          div.className = 'search-item';
          const typeRu =
            item.type === 'teacher'
              ? 'Преподаватель'
              : item.type === 'classroom'
              ? 'Аудитория'
              : 'Группа';

          div.innerHTML = `
            <div class="search-item-info">
              <span class="search-item-name">${item.name}</span>
              <span class="search-item-type">${typeRu}</span>
            </div>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg>
          `;

          div.addEventListener('click', () => {
            haptic('medium');
            closeSearch();
            loadSchedule(item);
          });

          searchResultsEl.appendChild(div);
        });
      } catch (err) {
        searchResultsEl.innerHTML = `<div class="search-placeholder">Ошибка при поиске</div>`;
      }
    }, 200);
  });

  function getDeeplinkTarget() {

    try {
      const urlParams = new URLSearchParams(window.location.search);
      const type = urlParams.get('type');
      const uid = urlParams.get('uid');
      const name = urlParams.get('name');
      const week = urlParams.get('week');

      if (type && name) {
        return {
          type: type,
          uid: uid ? parseInt(uid) : 0,
          name: decodeURIComponent(name),
          week: week ? parseInt(week) : null,
        };
      }

      // Telegram WebApp start_param (t.me/bot?startapp=...)
      const startParam = tg?.initDataUnsafe?.start_param;
      if (startParam) {
        const parts = startParam.split('_');
        if (parts.length >= 2) {
          return {
            type: parts[0],
            uid: parseInt(parts[1]) || 0,
            name: parts.slice(2).join('_') || `${parts[0]}_${parts[1]}`,
            week: null,
          };
        }
      }
    } catch (e) {}
    return null;
  }

  async function initApp() {
    // Request permission to send messages (for users who open Mini App before /start)
    if (tg && typeof tg.requestWriteAccess === 'function') {
      try {
        tg.requestWriteAccess((allowed) => {
          if (allowed) {
            fetch(`/api/me?init_data=${encodeURIComponent(state.initData)}`).catch(() => {});
          }
        });
      } catch (e) {}
    }

    const todayWd = new Date().getDay();
    state.selectedDay = todayWd === 0 ? 1 : todayWd;

    // Check for Deeplink directly from bot inline button or link
    const deeplink = getDeeplinkTarget();
    if (deeplink) {
      const todayISO = getLocalDateISO();
      await loadSchedule(
        { type: deeplink.type, uid: deeplink.uid, name: deeplink.name },
        deeplink.week,
        deeplink.week ? null : todayISO
      );
      return;
    }

    // 1. Instant load from local cache if available (0 ms response!)
    try {
      const cached = localStorage.getItem('cached_fav_schedule');

      if (cached) {
        const parsed = JSON.parse(cached);
        if (parsed.entity && parsed.days) {
          state.currentEntity = parsed.entity;
          state.weekDays = parsed.days;
          state.datesSummary = parsed.datesSummary || {};
          state.selectedWeek = parsed.week || 1;
          const todayWd = new Date().getDay();
          state.selectedDay = todayWd === 0 ? 1 : todayWd;
          updateHeader();
          updateWeekBar();
          renderDayRibbon();
          renderLessons();
        }
      }
    } catch (e) {}


    // 2. Fetch user profile and favorite
    try {
      const meRes = await fetch(`/api/me?init_data=${encodeURIComponent(state.initData)}`);
      if (meRes.ok) {
        state.user = await meRes.json();
        if (state.user?.is_admin) {
          btnAdminEl.classList.remove('hidden');
        }
        if (state.user.favorite_item) {
          const todayISO = getLocalDateISO();
          await loadSchedule(state.user.favorite_item, null, todayISO);
          return;
        }
      }
    } catch (e) {}

    if (!state.currentEntity) {
      openSearch();
    }
  }

  // ==================== ADMIN PANEL LOGIC ====================
  function switchAdminTab(activeTabBtn, activeView) {
    [tabBtnStats, tabBtnMaintenance, tabBtnBroadcast].forEach((b) => b.classList.remove('active'));
    [adminViewStats, adminViewMaintenance, adminViewBroadcast].forEach((v) => {
      v.classList.remove('active');
      v.classList.add('hidden');
    });
    activeTabBtn.classList.add('active');
    activeView.classList.remove('hidden');
    activeView.classList.add('active');
  }

  tabBtnStats.addEventListener('click', () => switchAdminTab(tabBtnStats, adminViewStats));
  tabBtnMaintenance.addEventListener('click', () => switchAdminTab(tabBtnMaintenance, adminViewMaintenance));
  tabBtnBroadcast.addEventListener('click', () => switchAdminTab(tabBtnBroadcast, adminViewBroadcast));

  function openAdminModal() {
    haptic('medium');
    adminModalEl.classList.remove('hidden');
    loadAdminStats();
  }

  function closeAdminModal() {
    adminModalEl.classList.add('hidden');
  }

  btnAdminEl.addEventListener('click', openAdminModal);
  adminBtnCloseEl.addEventListener('click', closeAdminModal);
  const adminOverlayEl = document.getElementById('adminOverlay');
  if (adminOverlayEl) {
    adminOverlayEl.addEventListener('click', closeAdminModal);
  }
  adminModalEl.addEventListener('click', (e) => {
    if (e.target === adminModalEl) closeAdminModal();
  });


  async function loadAdminStats() {
    try {
      const res = await fetch(`/api/admin/stats?init_data=${encodeURIComponent(state.initData)}`, {
        headers: { 'X-Telegram-Init-Data': state.initData },
      });
      if (!res.ok) {
        if (res.status === 403) showToast('⛔ Доступ запрещён (не админ)');
        return;
      }
      const data = await res.json();

      // Activity (DAU / WAU / MAU)
      const statDauEl = document.getElementById('statDau');
      const statWauEl = document.getElementById('statWau');
      const statMauEl = document.getElementById('statMau');
      const statNewTodayEl = document.getElementById('statNewToday');
      const statNewWeekEl = document.getElementById('statNewWeek');
      const statNewMonthEl = document.getElementById('statNewMonth');
      if (statDauEl) statDauEl.textContent = data.dau ?? 0;
      if (statWauEl) statWauEl.textContent = data.wau ?? 0;
      if (statMauEl) statMauEl.textContent = data.mau ?? 0;
      if (statNewTodayEl) statNewTodayEl.textContent = `+${data.new_today ?? 0} новых`;
      if (statNewWeekEl) statNewWeekEl.textContent = `+${data.new_week ?? 0} новых`;
      if (statNewMonthEl) statNewMonthEl.textContent = `+${data.new_month ?? 0} новых`;

      // Base & Conversions
      statTotalUsersEl.textContent = data.total_users ?? 0;
      statFavUsersEl.textContent = data.users_with_favorite ?? 0;
      statNotifyUsersEl.textContent = data.users_with_notifications ?? 0;
      const statFavRateEl = document.getElementById('statFavRate');
      const statNotifyRateEl = document.getElementById('statNotifyRate');
      if (statFavRateEl) statFavRateEl.textContent = data.fav_rate || '0%';
      if (statNotifyRateEl) statNotifyRateEl.textContent = data.notify_rate || '0%';

      // Distribution Bar & Totals
      const statTotalRequestsEl = document.getElementById('statTotalRequests');
      if (statTotalRequestsEl) statTotalRequestsEl.textContent = data.total_requests ?? 0;

      const pcts = data.type_percentages || { group: 0, teacher: 0, classroom: 0 };
      const dist = data.type_distribution || { group: 0, teacher: 0, classroom: 0 };
      const distBarGroup = document.getElementById('distBarGroup');
      const distBarTeacher = document.getElementById('distBarTeacher');
      const distBarClassroom = document.getElementById('distBarClassroom');
      if (distBarGroup) distBarGroup.style.width = `${pcts.group}%`;
      if (distBarTeacher) distBarTeacher.style.width = `${pcts.teacher}%`;
      if (distBarClassroom) distBarClassroom.style.width = `${pcts.classroom}%`;

      const distTextGroup = document.getElementById('distTextGroup');
      const distTextTeacher = document.getElementById('distTextTeacher');
      const distTextClassroom = document.getElementById('distTextClassroom');
      if (distTextGroup) distTextGroup.textContent = `${dist.group} (${pcts.group}%)`;
      if (distTextTeacher) distTextTeacher.textContent = `${dist.teacher} (${pcts.teacher}%)`;
      if (distTextClassroom) distTextClassroom.textContent = `${dist.classroom} (${pcts.classroom}%)`;

      // Top notification times
      const topNotifListEl = document.getElementById('topNotifList');
      if (topNotifListEl) {
        if (!data.top_notification_times || data.top_notification_times.length === 0) {
          topNotifListEl.innerHTML = '<span class="top-empty">Нет настроенных рассылок</span>';
        } else {
          topNotifListEl.innerHTML = data.top_notification_times
            .map((t) => `<span class="admin-chip">🔔 ${t.time} (<b>${t.count}</b> чел.)</span>`)
            .join('');
        }
      }

      const renderTop = (el, items) => {
        if (!items || items.length === 0) {
          el.innerHTML = '<div class="top-empty">Нет данных</div>';
          return;
        }
        el.innerHTML = items
          .map(
            (it) => `
          <div class="top-item-row">
            <span class="top-item-name">${it.name}</span>
            <span class="top-item-count">${it.count}</span>
          </div>
        `
          )
          .join('');
      };

      renderTop(topGroupsListEl, data.top_groups);
      renderTop(topTeachersListEl, data.top_teachers);
      renderTop(topClassroomsListEl, data.top_classrooms);

      maintSwitchEl.checked = Boolean(data.maintenance_mode);
      maintMessageInputEl.value = data.maintenance_message || '';
    } catch (e) {
      showToast('Ошибка загрузки админ-статистики');
    }
  }


  btnSaveMaintenanceEl.addEventListener('click', async () => {
    haptic('medium');
    try {
      const payload = {
        enabled: maintSwitchEl.checked,
        message: maintMessageInputEl.value.trim() || null,
      };
      const res = await fetch(`/api/admin/maintenance?init_data=${encodeURIComponent(state.initData)}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Telegram-Init-Data': state.initData,
        },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        maintAlertEl.textContent = '✅ Статус техобслуживания сохранён!';
        maintAlertEl.className = 'admin-status-alert success';
        maintAlertEl.classList.remove('hidden');
        setTimeout(() => maintAlertEl.classList.add('hidden'), 3500);
      } else {
        throw new Error();
      }
    } catch (e) {
      maintAlertEl.textContent = '❌ Ошибка сохранения статуса';
      maintAlertEl.className = 'admin-status-alert error';
      maintAlertEl.classList.remove('hidden');
    }
  });

  let currentUploadedMedia = null;


    if (bcFileInputEl) {
      bcFileInputEl.addEventListener('change', async (e) => {
        const file = e.target.files?.[0];
        if (!file) return;

        bcUploadStatusEl.classList.remove('hidden');
        bcUploadStatusEl.innerHTML = `⏳ Загрузка «${file.name}»...`;

        try {
          const res = await fetch(`/api/admin/upload?filename=${encodeURIComponent(file.name)}&init_data=${encodeURIComponent(state.initData)}`, {
            method: 'POST',
            headers: {
              'X-Telegram-Init-Data': state.initData,
            },
            body: file,
          });

          if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || 'Ошибка загрузки');
          }

          const data = await res.json();
          currentUploadedMedia = data;
          bcMediaUrlInputEl.value = data.url;
          bcUploadStatusEl.innerHTML = `✅ ${data.media_type === 'video' ? 'Видео' : 'Фото'} прикреплено: <b>${data.filename}</b> <span style="cursor:pointer;margin-left:8px;color:#ff3b30;font-weight:bold;" id="bcRemoveMedia" title="Удалить">✕</span>`;

          document.getElementById('bcRemoveMedia')?.addEventListener('click', () => {
            currentUploadedMedia = null;
            bcFileInputEl.value = '';
            bcMediaUrlInputEl.value = '';
            bcUploadStatusEl.classList.add('hidden');
            updateTelegramPreview();
          });

          updateTelegramPreview();
        } catch (err) {
          bcUploadStatusEl.innerHTML = `❌ Ошибка: ${err.message}`;
        }
      });
    }

    function updateTelegramPreview() {
      if (!tgPreviewTextEl) return;

      // 1. Text
      const rawText = bcTextInputEl.value.trim();
      if (rawText) {
        tgPreviewTextEl.innerHTML = rawText.replace(/\n/g, '<br>');
      } else {
        tgPreviewTextEl.textContent = 'Текст сообщения появится здесь...';
      }

      // 2. Time
      const now = new Date();
      const hh = String(now.getHours()).padStart(2, '0');
      const mm = String(now.getMinutes()).padStart(2, '0');
      tgPreviewTimeEl.textContent = `${hh}:${mm}`;

      // 3. Media
      const mediaUrl = bcMediaUrlInputEl.value.trim();
      if (mediaUrl) {
        tgPreviewMediaEl.classList.remove('hidden');
        const isVid = (currentUploadedMedia?.media_type === 'video') || /\.(mp4|mov|avi|webm|mkv|m4v)(\?.*)?$/i.test(mediaUrl);
        if (isVid) {
          tgPreviewMediaEl.innerHTML = `<video src="${mediaUrl}" controls playsinline style="max-height:220px;width:100%;border-radius:10px;display:block;"></video>`;
        } else {
          tgPreviewMediaEl.innerHTML = `<img src="${mediaUrl}" alt="Медиа" style="max-height:220px;width:100%;border-radius:10px;object-fit:cover;display:block;" onerror="this.parentElement.classList.add('hidden')">`;
        }
      } else {
        tgPreviewMediaEl.classList.add('hidden');
        tgPreviewMediaEl.innerHTML = '';
      }

      // 4. Inline button
      const btnText = bcBtnTextInputEl.value.trim();
      if (btnText) {
        tgPreviewBtnWrapperEl.classList.remove('hidden');
        tgPreviewBtnTextEl.textContent = btnText;
      } else {
        tgPreviewBtnWrapperEl.classList.add('hidden');
      }
    }

    bcTextInputEl.addEventListener('input', updateTelegramPreview);
    bcMediaUrlInputEl.addEventListener('input', () => {
      currentUploadedMedia = null;
      updateTelegramPreview();
    });
    bcBtnTextInputEl.addEventListener('input', updateTelegramPreview);
    bcBtnUrlInputEl.addEventListener('input', updateTelegramPreview);

    // Initial trigger
    updateTelegramPreview();

    async function handleBroadcast(isTest) {
      const text = bcTextInputEl.value.trim();
      if (!text) {
        bcAlertEl.textContent = 'Пожалуйста, введите текст сообщения';
        bcAlertEl.className = 'admin-status-alert error';
        bcAlertEl.classList.remove('hidden');
        return;
      }

      haptic('medium');
      const mediaUrl = bcMediaUrlInputEl.value.trim();
      const payload = {
        text,
        media_url: mediaUrl || null,
        media_type: currentUploadedMedia?.media_type || (/\.(mp4|mov|avi|webm|mkv|m4v)(\?.*)?$/i.test(mediaUrl) ? 'video' : 'image'),
        button_text: bcBtnTextInputEl.value.trim() || null,
        button_url: bcBtnUrlInputEl.value.trim() || null,
        test_only: isTest,
      };

      try {
        const res = await fetch(`/api/admin/broadcast?init_data=${encodeURIComponent(state.initData)}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Telegram-Init-Data': state.initData,
          },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (res.ok) {
          bcAlertEl.textContent = data.message || (isTest ? 'Тест отправлен вам в ЛС!' : 'Рассылка запущена!');
          bcAlertEl.className = 'admin-status-alert success';
          bcAlertEl.classList.remove('hidden');
          if (!isTest) {
            bcTextInputEl.value = '';
            bcMediaUrlInputEl.value = '';
            bcBtnTextInputEl.value = '';
            bcBtnUrlInputEl.value = '';
            if (bcUploadStatusEl) bcUploadStatusEl.classList.add('hidden');
            currentUploadedMedia = null;
            updateTelegramPreview();
          }
        } else {
          bcAlertEl.textContent = data.detail || 'Ошибка отправки рассылки';
          bcAlertEl.className = 'admin-status-alert error';
          bcAlertEl.classList.remove('hidden');
        }
      } catch (e) {
        bcAlertEl.textContent = 'Ошибка сети при рассылке';
        bcAlertEl.className = 'admin-status-alert error';
        bcAlertEl.classList.remove('hidden');
      }
    }

    btnBcTestEl.addEventListener('click', () => handleBroadcast(true));
    btnBcSendAllEl.addEventListener('click', () => {
      if (confirm('Вы уверены, что хотите запустить рассылку ВСЕМ пользователям бота?')) {
        handleBroadcast(false);
      }
    });



  // Live status ticker: recalculates progress bars and timers every 10 seconds without rebuilding DOM
  setInterval(() => {
    const currentDayData = state.weekDays[state.selectedDay];
    const todayISO = getLocalDateISO();
    if (currentDayData?.date !== todayISO) return;


    const rawLessons = currentDayData?.lessons || [];
    updateLiveDayWidget(rawLessons, currentDayData?.date);

    // Update active lesson card in place
    const now = new Date();
    for (const l of rawLessons) {
      const { start, end } = getLessonTimes(l.start_time, l.end_time);
      if (now >= start && now <= end) {
        const totalMs = end - start;
        const elapsedMs = now - start;
        const pct = Math.min(100, Math.max(0, Math.round((elapsedMs / totalMs) * 100)));
        const rem = Math.max(1, Math.round((end - now) / 60000));
        const activeCard = scheduleSliderEl.querySelector('.lesson-card.active-lesson');
        if (activeCard) {
          const prog = activeCard.querySelector('.card-live-progress');
          if (prog) prog.style.width = `${pct}%`;
          const badge = activeCard.querySelector('.now-badge');
          if (badge) badge.innerHTML = `<span class="pulse-dot"></span>Идет (${rem} мин)`;
        }
      }
    }
  }, 10000);


  initApp();
})();

