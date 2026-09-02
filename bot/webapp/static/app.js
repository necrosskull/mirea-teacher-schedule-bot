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
  const nextLessonBannerEl = document.getElementById('nextLessonBanner');

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

  function isLessonNow(startTimeStr, endTimeStr, lessonDateStr) {
    try {
      const now = new Date();
      const todayISO = now.toISOString().split('T')[0];
      if (lessonDateStr && lessonDateStr !== todayISO) return false;

      const [sh, sm] = startTimeStr.split(':').map(Number);
      const [eh, em] = endTimeStr.split(':').map(Number);

      const start = new Date(now);
      start.setHours(sh, sm, 0, 0);

      const end = new Date(now);
      end.setHours(eh, em, 0, 0);

      return now >= start && now <= end;
    } catch (e) {
      return false;
    }
  }

  function getRemainingMinutes(endTimeStr) {
    try {
      const now = new Date();
      const [eh, em] = endTimeStr.split(':').map(Number);
      const end = new Date(now);
      end.setHours(eh, em, 0, 0);
      const diffMs = end - now;
      return Math.max(1, Math.round(diffMs / 60000));
    } catch (e) {
      return 0;
    }
  }

  function getMinutesUntilStart(startTimeStr) {
    try {
      const now = new Date();
      const [sh, sm] = startTimeStr.split(':').map(Number);
      const start = new Date(now);
      start.setHours(sh, sm, 0, 0);
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

  function updateNextLessonBanner(lessons, currentDateStr) {
    const todayISO = new Date().toISOString().split('T')[0];
    if (currentDateStr !== todayISO || !lessons || lessons.length === 0) {
      nextLessonBannerEl.classList.add('hidden');
      return;
    }

    let nextLesson = null;
    let minMinutes = 9999;

    for (const l of lessons) {
      const mins = getMinutesUntilStart(l.start_time);
      if (mins > 0 && mins < minMinutes && mins <= 90) {
        minMinutes = mins;
        nextLesson = l;
      }
    }

    if (nextLesson) {
      const room = nextLesson.classrooms && nextLesson.classrooms[0] ? ` • ауд. ${nextLesson.classrooms[0]}` : '';
      nextLessonBannerEl.innerHTML = `
        <span>⏳</span>
        <span>До пары осталось <b>${minMinutes} мин</b> (${nextLesson.start_time}${room})</span>
      `;
      nextLessonBannerEl.classList.remove('hidden');
    } else {
      nextLessonBannerEl.classList.add('hidden');
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

    updateNextLessonBanner(rawLessons, currentDayData?.date);

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

    lessons.forEach((lesson) => {
      const isNow = isLessonNow(lesson.start_time, lesson.end_time, currentDayData?.date);
      const badgeClass = getTypeBadgeClass(lesson.lesson_type);
      const typeName = getTypeDisplayName(lesson.lesson_type);

      const card = document.createElement('div');
      card.className = `lesson-card ${isNow ? 'active-lesson' : ''}`;

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
        <div class="lesson-card-header">
          <div class="lesson-time-wrap">
            <span class="lesson-number">${lesson.number}</span>
            <span class="lesson-time">${lesson.start_time} – ${lesson.end_time}</span>
          </div>
          ${
            isNow
              ? `<span class="now-badge"><span class="pulse-dot"></span>Идет (${getRemainingMinutes(lesson.end_time)} мин)</span>`
              : `<span class="lesson-type-badge ${badgeClass}">${typeName}</span>`
          }
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
      const res = await fetch(`/api/schedule?${query.toString()}`);
      if (!res.ok) throw new Error('Ошибка сети');

      const data = await res.json();
      state.weekDays = data.days || {};
      state.datesSummary = data.dates_summary || state.datesSummary || {};
      state.selectedWeek = data.week || targetWeek;
      state.currentWeek = data.current_week || 1;

      if (data.target_weekday && targetDay === null) {
        state.selectedDay = Math.min(6, Math.max(1, data.target_weekday));
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

    const todayISO = new Date().toISOString().split('T')[0];
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
    const todayISO = new Date().toISOString().split('T')[0];
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
    const todayISO = new Date().toISOString().split('T')[0];
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
        const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
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
          updateHeader();
          updateWeekBar();
          renderDayRibbon();
          renderLessons();
        }
      }
    } catch (e) {}

    const todayWd = new Date().getDay();
    state.selectedDay = todayWd === 0 ? 1 : todayWd;

    // 2. Fetch user profile and favorite
    try {
      const meRes = await fetch(`/api/me?init_data=${encodeURIComponent(state.initData)}`);
      if (meRes.ok) {
        state.user = await meRes.json();
        if (state.user.favorite_item) {
          await loadSchedule(state.user.favorite_item);
          return;
        }
      }
    } catch (e) {}

    if (!state.currentEntity) {
      openSearch();
    }
  }

  initApp();
})();
