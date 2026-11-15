const menuButton = document.getElementById('menu-btn');
const nav = document.getElementById('nav');

if (menuButton && nav) {
  menuButton.dataset.iconHint = menuButton.getAttribute('aria-label');
  const setOpen = (open) => {
    nav.classList.toggle('open', open);
    menuButton.setAttribute('aria-expanded', open ? 'true' : 'false');
    menuButton.setAttribute('aria-label', open ? 'Fechar menu' : 'Abrir menu');
    menuButton.dataset.iconHint = open ? 'Fechar menu' : 'Abrir menu';
  };

  menuButton.addEventListener('click', () => setOpen(!nav.classList.contains('open')));

  nav.addEventListener('click', (event) => {
    if (event.target.closest('a') && nav.classList.contains('open')) setOpen(false);
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && nav.classList.contains('open')) {
      setOpen(false);
      menuButton.focus();
    }
  });
}

const currentPath = window.location.pathname.replace(/\/+$/, '') || '/';
document.querySelectorAll('#nav a').forEach((link) => {
  const href = link.getAttribute('href');
  if (href && href === currentPath) {
    link.setAttribute('aria-current', 'page');
    const group = link.closest('.client-nav-more');
    if (group) group.open = true;
  }
});

const chatFormSelector = '[data-chat-form],[data-chat-start-form],form[action="/admin/chat-equipe"],form[action="/conversas/responder"],form[action="/atendimento/responder"],form[action="/admin/atendimento-visitante/responder"]';
const isChatForm = (form) => Boolean(form && form.matches && form.matches(chatFormSelector));

document.addEventListener('submit', (event) => {
  const form = event.target;
  if (!isChatForm(form)) return;
  if (form.dataset.submitting === '1') {
    event.preventDefault();
    return;
  }
  form.dataset.submitting = '1';
  const button = form.querySelector('button[type="submit"]');
  if (button) button.disabled = true;
}, true);

document.addEventListener('keydown', (event) => {
  if (event.key !== 'Enter' || event.shiftKey || event.ctrlKey || event.altKey || event.metaKey || event.isComposing) return;
  const textarea = event.target.closest('textarea');
  if (!textarea) return;
  const form = textarea.closest('form');
  if (!isChatForm(form) || form.dataset.submitting === '1') return;
  const file = form.querySelector('input[type="file"]');
  if (!textarea.value.trim() && !(file && file.files && file.files.length)) return;
  event.preventDefault();
  if (typeof form.requestSubmit === 'function') form.requestSubmit();
  else form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
});

const blSoundEnabled = () => {
  try {
    const stored = localStorage.getItem('bl-notif-sound');
    return stored === null ? true : stored === '1';
  } catch (error) { return true; }
};

const blPlaySound = () => {
  if (!blSoundEnabled()) return;
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    const play = () => {
      const oscillator = ctx.createOscillator();
      const gain = ctx.createGain();
      oscillator.type = 'sine';
      oscillator.frequency.setValueAtTime(740, ctx.currentTime);
      oscillator.frequency.exponentialRampToValueAtTime(980, ctx.currentTime + 0.12);
      gain.gain.setValueAtTime(0.0001, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.12, ctx.currentTime + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.2);
      oscillator.connect(gain);
      gain.connect(ctx.destination);
      oscillator.start();
      oscillator.stop(ctx.currentTime + 0.22);
      oscillator.addEventListener('ended', () => ctx.close());
    };
    if (ctx.state === 'suspended') ctx.resume().then(play).catch(() => ctx.close());
    else play();
  } catch (error) { /* áudio indisponível */ }
};

// Ícones para os tipos de aviso e indicadores.
const navigationIcons = {
  home: 'M3 10 12 3l9 7v10h-6v-6H9v6H3z',
  cases: 'M4 7h16v13H4z M9 7V5h6v2 M4 12h16',
  messages: 'M4 4h16v12H9l-5 4z M8 9h8 M8 12h5',
  documents: 'M6 3h9l3 3v15H6z M14 3v4h4 M9 11h6 M9 15h6',
  calendar: 'M4 6h16v14H4z M8 3v6 M16 3v6 M4 10h16 M8 14h3',
  tasks: 'M9 6h11 M9 12h11 M9 18h11 M4 6l1 1 2-2 M4 12l1 1 2-2 M4 18l1 1 2-2',
  updates: 'M4 12a8 8 0 1 0 2-5 M4 4v4h4 M12 8v4l3 2',
  pending: 'M12 3 3 20h18z M12 9v5 M12 17h.01',
  add: 'M12 4v16 M4 12h16',
  user: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M5 21a7 7 0 0 1 14 0',
  users: 'M9 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M2 21a7 7 0 0 1 14 0 M16 4a4 4 0 0 1 0 8 M18 14a7 7 0 0 1 4 7',
  security: 'M12 3 4 6v5c0 5 3 8 8 10 5-2 8-5 8-10V6z M9 12l2 2 4-4',
  settings: 'M4 7h16 M7 4v6 M4 17h16 M17 14v6',
  report: 'M4 20h16 M7 17v-5 M12 17V5 M17 17V9',
};
const makeNavIcon = (type) => {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('aria-hidden', 'true');
  svg.classList.add('nav-icon');
  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('d', navigationIcons[type]);
  svg.appendChild(path);
  return svg;
};
document.querySelectorAll('.client-nav a, .admin-nav a').forEach((link) => {
  if (link.closest('.admin-nav') && link.getAttribute('href') === currentPath) {
    link.setAttribute('aria-current', 'page');
    const group = link.closest('.admin-nav-more');
    if (group) group.querySelector('summary').classList.add('current');
  }
});

document.querySelectorAll('form').forEach((form) => {
  const client = form.querySelector('[data-context-client]');
  const cases = form.querySelector('[data-context-case]');
  if (!client || !cases) return;
  const filterCases = () => {
    Array.from(cases.options).forEach((option) => {
      if (!option.value) return;
      const matches = Boolean(client.value) && option.dataset.clientId === client.value;
      option.hidden = !matches;
      option.disabled = !matches;
    });
    if (cases.selectedOptions.length && cases.selectedOptions[0].disabled) cases.value = '';
  };
  client.addEventListener('change', filterCases);
  filterCases();
});

document.querySelectorAll('form[action="/admin/delete"]').forEach((form) => {
  form.addEventListener('submit', (event) => {
    if (!window.confirm('Mover este registro para a lixeira? Ele poderá ser restaurado.')) event.preventDefault();
  });
});

document.querySelectorAll('.kpi, .client-kpi').forEach((item) => {
  const label = item.querySelector('.kpi-label') || item.querySelector('span');
  const text = label ? label.textContent.toLowerCase() : '';
  let type = 'report';
  if (text.includes('mensagen') || text.includes('relato') || text.includes('contato')) type = 'messages';
  else if (text.includes('document')) type = 'documents';
  else if (text.includes('solicita') || text.includes('aguardando') || text.includes('pendênc')) type = 'pending';
  else if (text.includes('responsável')) type = 'users';
  else if (text.includes('andamento') || text.includes('movimentação')) type = 'updates';
  else if (text.includes('conclu')) type = 'security';
  else if (text.includes('caso')) type = 'cases';
  const icon = makeNavIcon(type);
  icon.classList.add('kpi-icon');
  item.prepend(icon);
});

const updateConversationCounters = (data) => {
  if (Number.isFinite(Number(data.unread_client))) {
    document.querySelectorAll('[data-unread-client], [data-unread-count]').forEach((el) => { el.textContent = String(data.unread_client); });
  }
  if (Number.isFinite(Number(data.unread_internal))) {
    document.querySelectorAll('[data-unread-internal]').forEach((el) => {
      el.textContent = String(data.unread_internal);
      const card = el.closest('[data-hide-zero]');
      if (card) card.hidden = Number(data.unread_internal) === 0;
    });
  }
  if (data.new_contacts !== null && Number.isFinite(Number(data.new_contacts))) {
    document.querySelectorAll('[data-new-contacts]').forEach((el) => {
      el.textContent = String(data.new_contacts);
      const card = el.closest('[data-hide-zero]');
      if (card) card.hidden = Number(data.new_contacts) === 0;
    });
  }
};

const notifWrap = document.getElementById('notif-wrap');
if (notifWrap) {
  const notifButton = document.getElementById('notif-btn');
  const notifPanel = document.getElementById('notif-panel');
  const notifCount = document.getElementById('notif-count');
  const notifList = document.getElementById('notif-list');
  const notifReadAll = document.getElementById('notif-read-all');
  const notifEnable = document.getElementById('notif-enable');
  const notifSound = document.getElementById('notif-sound');
  const notifClose = document.getElementById('notif-close');
  const notifSummary = document.getElementById('notif-summary');
  const notifStatus = document.getElementById('notif-status');
  const notifFilterAll = document.getElementById('notif-filter-all');
  const notifFilterUnread = document.getElementById('notif-filter-unread');
  const notifToasts = document.getElementById('notif-toasts');
  notifButton.dataset.iconHint = 'Notificações';
  notifClose.dataset.iconHint = 'Fechar notificações';
  const csrfMeta = document.querySelector('meta[name="csrf-token"]');
  const csrfToken = csrfMeta ? csrfMeta.content : '';
  const seenIds = new Set();
  const notificationTypes = {
    message: ['Mensagens', 'messages'], internal: ['Relato interno', 'messages'], mention: ['Menção', 'messages'],
    document: ['Documentos', 'documents'], appointment: ['Compromissos', 'calendar'],
    pendency: ['Pendências', 'pending'], waiting_client: ['Pendências', 'pending'],
    case: ['Atendimentos', 'cases'], stale_case: ['Atendimentos', 'cases'],
    request: ['Solicitações', 'messages'], stale_request: ['Solicitações', 'pending'],
    update: ['Atualizações', 'updates'], client: ['Clientes', 'users'], contact: ['Contato do site', 'messages'], task: ['Tarefas', 'tasks'],
  };
  let currentItems = [];
  let currentUnread = 0;
  let filter = 'all';
  let firstLoad = true;
  const baseTitle = document.title;
  let titleAlertTimer = null;
  let titleAlertCount = 0;
  let iconLink = document.querySelector('link[rel="icon"]');
  if (!iconLink) {
    iconLink = document.createElement('link');
    iconLink.rel = 'icon';
    iconLink.type = 'image/svg+xml';
    document.head.appendChild(iconLink);
  }
  const baseFavicon = iconLink.getAttribute('href') || '/static/favicon.svg';
  const alertFavicon = 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><circle cx="32" cy="32" r="30" fill="#1e8e3e"/><text x="32" y="44" text-anchor="middle" font-family="Arial" font-size="36" font-weight="bold" fill="#fff">!</text></svg>');
  const restoreTitle = () => {
    document.title = currentUnread ? `(${currentUnread}) ${baseTitle}` : baseTitle;
  };
  const stopTitleAlert = (keepCount = false) => {
    if (titleAlertTimer) {
      window.clearInterval(titleAlertTimer);
      titleAlertTimer = null;
    }
    iconLink.setAttribute('href', baseFavicon);
    if (keepCount) restoreTitle();
    else document.title = baseTitle;
  };
  const startTitleAlert = (count) => {
    titleAlertCount = Math.max(1, Number(count) || 1);
    if (titleAlertTimer) return;
    let highlighted = false;
    const tick = () => {
      highlighted = !highlighted;
      document.title = highlighted
        ? `\uD83D\uDFE2 ${titleAlertCount} nova notifica\u00e7\u00e3o \u2014 ${baseTitle}`
        : `(${titleAlertCount}) ${baseTitle}`;
      iconLink.setAttribute('href', highlighted ? alertFavicon : baseFavicon);
    };
    tick();
    titleAlertTimer = window.setInterval(tick, 900);
  };
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && titleAlertTimer) stopTitleAlert(true);
  });

  const setPanel = (open, returnFocus = false) => {
    notifPanel.hidden = !open;
    notifButton.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (returnFocus) notifButton.focus();
  };

  const markRead = async (id) => {
    const body = new URLSearchParams();
    body.set('csrf', csrfToken);
    if (id !== null) {
      body.set('id', String(id));
    } else {
      body.set('all', '1');
    }
    const response = await fetch('/notificacoes/ler', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body,
    });
    if (!response.ok) throw new Error('Falha ao atualizar avisos');
  };

  const formatDate = (value) => {
    const raw = String(value || '').trim();
    if (!raw) return '';
    let normalized = raw.replace(' ', 'T');
    normalized = normalized.replace(/(\.\d{3})\d+/, '$1');
    normalized = normalized.replace(/([+-]\d{2})$/, '$1:00');
    if (!/[zZ]|[+-]\d{2}:?\d{2}$/.test(normalized)) normalized += 'Z';
    const parsed = new Date(normalized);
    if (Number.isNaN(parsed.getTime())) return raw;
    return new Intl.DateTimeFormat('pt-BR', {
      timeZone: 'America/Sao_Paulo',
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit', hour12: false,
    }).format(parsed).replace(',', ' às');
  };

  const renderList = () => {
    const activeId = document.activeElement && document.activeElement.dataset.notificationId;
    const items = filter === 'unread' ? currentItems.filter((item) => item.unread) : currentItems;
    notifFilterAll.setAttribute('aria-pressed', filter === 'all' ? 'true' : 'false');
    notifFilterUnread.setAttribute('aria-pressed', filter === 'unread' ? 'true' : 'false');
    notifList.replaceChildren();
    if (!items.length) {
      const empty = document.createElement('p');
      empty.className = 'notif-empty';
      empty.textContent = filter === 'unread' && currentUnread
        ? 'Há avisos não lidos anteriores aos 20 mais recentes.'
        : filter === 'unread' ? 'Nenhum aviso não lido.' : 'Nenhuma notificação no momento.';
      notifList.appendChild(empty);
    }
    items.forEach((item) => {
      const info = notificationTypes[item.type] || ['Aviso', 'updates'];
      const link = document.createElement('a');
      link.className = 'notif-item' + (item.unread ? ' unread' : '');
      let target = '';
      if (typeof item.url === 'string' && item.url.startsWith('/')) {
        try {
          const destination = new URL(item.url, window.location.href);
          if (destination.origin === window.location.origin) target = destination.pathname + destination.search + destination.hash;
        } catch (error) { /* A notification without a valid destination remains in the list. */ }
      }
      link.href = target || '#';
      link.dataset.notificationId = String(item.id);
      const icon = makeNavIcon(info[1]);
      icon.classList.add('notif-item-icon');
      const content = document.createElement('span');
      content.className = 'notif-item-content';
      const meta = document.createElement('span');
      meta.className = 'notif-item-meta';
      meta.textContent = info[0] + (item.unread ? ' · Não lida' : ' · Lida');
      const title = document.createElement('strong');
      title.textContent = item.title || 'Notificação';
      const detail = document.createElement('small');
      detail.textContent = item.body || '';
      const time = document.createElement('time');
      time.textContent = formatDate(item.created);
      content.append(meta, title, detail, time);
      link.append(icon, content);
      link.addEventListener('click', async (event) => {
        if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        if (target.startsWith('/conversas/') && window.openConversation) {
          setPanel(false);
          await window.openConversation(target, notifButton);
          return;
        }
        if (item.unread) {
          try {
            await markRead(item.id);
          } catch (error) {
            notifStatus.textContent = 'Não foi possível marcar o aviso como lido.';
            if (!target) return;
          }
        }
        if (target) window.location.href = target;
        else loadNotifications();
      });
      notifList.appendChild(link);
    });
    if (activeId) {
      const replacement = Array.from(notifList.querySelectorAll('[data-notification-id]'))
        .find((item) => item.dataset.notificationId === activeId);
      if (replacement) replacement.focus({ preventScroll: true });
    }
  };

  const showToast = (items) => {
    if (!items.length) return;
    blPlaySound();
    const toast = document.createElement('div');
    toast.className = 'notif-toast';
    const open = document.createElement('button');
    open.type = 'button';
    open.className = 'notif-toast-open';
    const type = items.length === 1 && notificationTypes[items[0].type];
    open.appendChild(makeNavIcon(type ? type[1] : 'updates'));
    const text = document.createElement('span');
    const title = document.createElement('strong');
    title.textContent = items.length === 1 ? 'Novo aviso' : `${items.length} novos avisos`;
    const description = document.createElement('small');
    description.textContent = items.length === 1 ? (items[0].title || 'Nova notificação') : 'Abra a central de notificações';
    text.append(title, description);
    open.appendChild(text);
    open.addEventListener('click', async () => {
      toast.remove();
      const target = items.length === 1 && typeof items[0].url === 'string' && items[0].url.startsWith('/') ? items[0].url : '';
      if (target.startsWith('/conversas/') && window.openConversation) {
        await window.openConversation(target, notifButton);
        return;
      }
      if (target) {
        const single = items.length === 1 ? items[0] : null;
        if (single && single.unread) {
          try { await markRead(single.id); } catch (error) { /* segue para o item */ }
        }
        window.location.href = target;
        return;
      }
      setPanel(true);
      notifButton.focus();
      loadNotifications();
    });
    const dismiss = document.createElement('button');
    dismiss.type = 'button';
    dismiss.className = 'notif-toast-dismiss';
    dismiss.setAttribute('aria-label', 'Fechar aviso');
    dismiss.textContent = '×';
    dismiss.addEventListener('click', () => toast.remove());
    toast.append(open, dismiss);
    notifToasts.replaceChildren(toast);
    window.setTimeout(() => {
      if (!toast.contains(document.activeElement)) toast.remove();
    }, 10000);
  };

  const browserNotificationsEnabled = () => {
    try {
      const stored = localStorage.getItem('bl-browser-notify');
      return stored === null ? true : stored === '1';
    } catch (error) { return true; }
  };

  const render = (data) => {
    const items = Array.isArray(data.items) ? data.items : [];
    const unread = Math.max(0, Number(data.unread) || 0);
    const newItems = firstLoad ? [] : items.filter((item) => item.unread && !seenIds.has(item.id));
    currentItems = items;
    currentUnread = unread;
    updateConversationCounters(data);
    notifCount.textContent = unread > 99 ? '99+' : String(unread);
    notifCount.hidden = unread === 0;
    notifButton.setAttribute('aria-label', unread ? `Notificações: ${unread} não lida${unread === 1 ? '' : 's'}` : 'Notificações: nenhuma não lida');
    notifSummary.textContent = unread ? `${unread} aviso${unread === 1 ? '' : 's'} não lido${unread === 1 ? '' : 's'}` : 'Tudo em dia';
    notifReadAll.disabled = unread === 0;
    notifStatus.textContent = '';
    renderList();
    showToast(newItems);
    if (newItems.length) startTitleAlert(unread);
    else if (unread === 0) stopTitleAlert();
    if (browserNotificationsEnabled() && 'Notification' in window && Notification.permission === 'granted') {
      newItems.slice(0, 3).forEach((item) => {
        try {
          const browserNotice = new Notification(item.title, { body: item.body || '', tag: 'bl-notification-' + item.id });
          browserNotice.onclick = () => {
            window.focus();
            if (typeof item.url === 'string' && item.url.startsWith('/')) window.location.href = item.url;
            browserNotice.close();
          };
        } catch (error) {
          /* ignore */
        }
      });
    }
    items.forEach((item) => seenIds.add(item.id));
    firstLoad = false;
  };

  const loadNotifications = async () => {
    try {
      const response = await fetch('/notificacoes', { credentials: 'same-origin', headers: { Accept: 'application/json' } });
      if (!response.ok) throw new Error('Falha ao carregar');
      render(await response.json());
    } catch (error) {
      notifStatus.textContent = 'Não foi possível atualizar as notificações. Tente novamente.';
      if (firstLoad) {
        notifSummary.textContent = 'Atualização indisponível';
        notifList.replaceChildren();
      }
    }
  };

  notifButton.addEventListener('click', async () => {
    const open = notifPanel.hidden;
    setPanel(open);
    if (open) {
      stopTitleAlert(true);
      if ('Notification' in window && Notification.permission === 'default') {
        try {
          const permission = await Notification.requestPermission();
          if (permission === 'granted') {
            localStorage.setItem('bl-browser-notify', '1');
            notifEnable.textContent = 'Alertas do navegador ativados';
          }
        } catch (error) { /* permissao indisponivel */ }
      }
      loadNotifications();
    }
  });
  notifClose.addEventListener('click', () => setPanel(false, true));
  notifFilterAll.addEventListener('click', () => { filter = 'all'; renderList(); });
  notifFilterUnread.addEventListener('click', () => { filter = 'unread'; renderList(); });

  notifReadAll.addEventListener('click', async () => {
    notifReadAll.disabled = true;
    try {
      await markRead(null);
      await loadNotifications();
      stopTitleAlert();
    } catch (error) {
      notifStatus.textContent = 'Não foi possível marcar os avisos como lidos. Tente novamente.';
      notifReadAll.disabled = false;
    }
  });

  const refreshSoundLabel = () => {
    if (notifSound) notifSound.textContent = blSoundEnabled() ? 'Som: ativado' : 'Som: desativado';
  };
  if (notifSound) {
    refreshSoundLabel();
    notifSound.addEventListener('click', () => {
      try {
        localStorage.setItem('bl-notif-sound', blSoundEnabled() ? '0' : '1');
        refreshSoundLabel();
        if (blSoundEnabled()) blPlaySound();
      } catch (error) {
        notifStatus.textContent = 'Não foi possível salvar a preferência de som.';
      }
    });
  }

  notifEnable.addEventListener('click', async () => {
    if (!('Notification' in window)) {
      notifEnable.textContent = 'Navegador sem suporte';
      return;
    }
    let permission;
    try { permission = await Notification.requestPermission(); }
    catch (error) { notifStatus.textContent = 'Não foi possível solicitar a permissão do navegador.'; return; }
    if (permission === 'granted') {
      try {
        localStorage.setItem('bl-browser-notify', '1');
        notifEnable.textContent = 'Alertas do navegador ativados';
      } catch (error) {
        notifStatus.textContent = 'Não foi possível salvar a preferência neste navegador.';
      }
    } else {
      notifEnable.textContent = 'Permissão não concedida';
    }
  });

  if (browserNotificationsEnabled() && 'Notification' in window && Notification.permission === 'granted') {
    notifEnable.textContent = 'Alertas do navegador ativados';
  }

  document.addEventListener('click', (event) => {
    if (!notifWrap.contains(event.target)) setPanel(false);
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !notifPanel.hidden) setPanel(false, true);
  });

  loadNotifications();
  window.setInterval(loadNotifications, 5000);
  window.addEventListener('conversation:read', loadNotifications);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) loadNotifications(); });
}

// O link continua funcionando como página normal em navegadores sem diálogo.
const readConversation = async (view) => {
  const markForm = view.querySelector('form[action="/conversas/ler"]');
  if (!markForm) return;
  try {
    const response = await fetch(markForm.action, {
      method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json' },
      body: new URLSearchParams(new FormData(markForm)),
    });
    if (!response.ok) throw new Error('Falha ao registrar leitura');
    const data = await response.json();
    updateConversationCounters(data);
    document.querySelectorAll(`[data-conversation-link][href="/conversas/${view.dataset.conversationId}"] .conversation-unread`).forEach((el) => {
      if (data.conversation_unread) el.textContent = `${data.conversation_unread} não lida(s)`;
      else el.remove();
    });
    markForm.remove();
    window.dispatchEvent(new Event('conversation:read'));
  } catch (error) {
    const warning = document.createElement('p');
    warning.className = 'conversation-error';
    warning.textContent = 'Não foi possível atualizar a leitura. Use o botão para tentar novamente.';
    markForm.before(warning);
  }
};

const initialConversation = document.querySelector('#conversation-view');
if (initialConversation) readConversation(initialConversation);

if (typeof HTMLDialogElement !== 'undefined' && HTMLDialogElement.prototype.showModal) {
  const dialog = document.createElement('dialog');
  dialog.className = 'conversation-dialog';
  dialog.setAttribute('aria-label', 'Conversa');
  document.body.appendChild(dialog);
  let previousFocus = null;
  let conversationChanged = false;
  dialog.addEventListener('close', () => {
    dialog.replaceChildren();
    if (conversationChanged) { window.location.reload(); return; }
    if (previousFocus && previousFocus.isConnected) previousFocus.focus();
  });

  const displayConversation = async (url) => {
    const response = await fetch(url, { credentials: 'same-origin' });
    if (!response.ok) throw new Error('Conversa indisponível');
    const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
    const view = doc.querySelector('#conversation-view');
    if (!view) throw new Error('Conversa indisponível');
    const close = document.createElement('button');
    close.type = 'button';
    close.className = 'conversation-dialog-close';
    close.setAttribute('aria-label', 'Fechar conversa');
    close.dataset.iconHint = 'Fechar conversa';
    close.textContent = '×';
    close.addEventListener('click', () => dialog.close());
    dialog.replaceChildren(close, document.importNode(view, true));
    dialog.querySelectorAll('form').forEach((form) => {
      if (form.action.endsWith('/conversas/ler')) return;
      form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const submit = form.querySelector('button[type="submit"]');
        if (submit) submit.disabled = true;
        try {
          const multipart = form.enctype === 'multipart/form-data';
          const payload = multipart ? new FormData(form) : new URLSearchParams(new FormData(form));
          const options = { method: 'POST', credentials: 'same-origin', body: payload };
          if (!multipart) options.headers = { 'Content-Type': 'application/x-www-form-urlencoded' };
          const result = await fetch(form.action, options);
          if (!result.ok) throw new Error('Não foi possível concluir a operação.');
          conversationChanged = true;
          await displayConversation(url);
          await readConversation(dialog.querySelector('#conversation-view'));
        } catch (error) {
          const warning = document.createElement('p');
          warning.className = 'conversation-error';
          warning.setAttribute('role', 'alert');
          warning.textContent = 'Não foi possível concluir a operação. Verifique sua conexão e tente novamente.';
          form.prepend(warning);
          if (submit) submit.disabled = false;
          form.dataset.submitting = '';
        }
      });
    });
  };

  window.openConversation = async (url, trigger) => {
    previousFocus = trigger || document.activeElement;
    try {
      await displayConversation(url);
      if (!dialog.open) dialog.showModal();
      dialog.querySelector('.conversation-dialog-close').focus();
      await readConversation(dialog.querySelector('#conversation-view'));
    } catch (error) {
      window.location.href = url;
    }
  };
  document.addEventListener('click', (event) => {
    const link = event.target.closest('a[data-conversation-link]');
    if (!link || event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    window.openConversation(link.href, link);
  });
}

// Fotos ampliadas permanecem na página; o link direto funciona sem JavaScript.
if (typeof HTMLDialogElement !== 'undefined' && HTMLDialogElement.prototype.showModal) {
  const photoDialog = document.createElement('dialog');
  photoDialog.className = 'photo-dialog';
  photoDialog.setAttribute('aria-labelledby', 'photo-dialog-caption');
  const closePhoto = document.createElement('button');
  closePhoto.type = 'button';
  closePhoto.className = 'photo-dialog-close';
  closePhoto.setAttribute('aria-label', 'Fechar foto ampliada');
  closePhoto.dataset.iconHint = 'Fechar foto';
  closePhoto.textContent = '×';
  const figure = document.createElement('figure');
  const image = document.createElement('img');
  const caption = document.createElement('figcaption');
  caption.id = 'photo-dialog-caption';
  figure.append(image, caption);
  photoDialog.append(closePhoto, figure);
  document.body.appendChild(photoDialog);
  let photoTrigger = null;
  closePhoto.addEventListener('click', () => photoDialog.close());
  photoDialog.addEventListener('click', (event) => {
    if (event.target === photoDialog) photoDialog.close();
  });
  photoDialog.addEventListener('close', () => {
    image.removeAttribute('src');
    if (photoTrigger && photoTrigger.isConnected) photoTrigger.focus();
  });
  document.addEventListener('click', (event) => {
    const link = event.target.closest('a[data-photo-lightbox]');
    if (!link || event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const url = new URL(link.href, window.location.href);
    if (url.origin !== window.location.origin || !url.pathname.startsWith('/static/img/')) return;
    event.preventDefault();
    photoTrigger = link;
    const description = link.dataset.photoCaption || 'Retrato institucional';
    image.src = url.href;
    image.alt = description;
    caption.textContent = description;
    if (!photoDialog.open) photoDialog.showModal();
    closePhoto.focus();
  });
}

// Menu lateral dos pain�is.
const panelMenu = document.getElementById('panel-menu');
const panelSidebar = document.getElementById('panel-sidebar');
const panelOverlay = document.getElementById('panel-overlay');
if (panelMenu && panelSidebar) {
  const setPanelMenu = (open) => {
    panelSidebar.classList.toggle('open', open);
    if (panelOverlay) panelOverlay.classList.toggle('open', open);
    panelMenu.setAttribute('aria-expanded', open ? 'true' : 'false');
    panelMenu.setAttribute('aria-label', open ? 'Fechar menu' : 'Abrir menu');
  };
  panelMenu.addEventListener('click', () => setPanelMenu(!panelSidebar.classList.contains('open')));
  if (panelOverlay) panelOverlay.addEventListener('click', () => setPanelMenu(false));
  panelSidebar.addEventListener('click', (event) => {
    if (event.target.closest('a') && panelSidebar.classList.contains('open')) setPanelMenu(false);
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && panelSidebar.classList.contains('open')) setPanelMenu(false);
  });
}

// Fecha o menu da conta ao clicar fora.
const panelUserMenus = document.querySelectorAll('.panel-user-menu');
document.addEventListener('click', (event) => {
  panelUserMenus.forEach((menu) => {
    if (menu.open && !menu.contains(event.target)) menu.open = false;
  });
});
document.querySelectorAll('form[action="/admin/tarefa/excluir"], form[action="/admin/documento-interno/excluir"]').forEach((form) => {
  form.addEventListener('submit', (event) => {
    if (!window.confirm('Remover este registro? Ele deixar� de aparecer nas listas.')) event.preventDefault();
  });
});
// Atualiza a conversa do visitante e o atendimento no painel.
const guestChat = document.getElementById('guest-chat');
if (guestChat && guestChat.dataset.guestEndpoint) {
  const guestThread = guestChat.querySelector('[data-guest-thread]');
  let guestHtml = guestThread ? guestThread.innerHTML : '';
  const refreshGuestChat = async () => {
    try {
      const response = await fetch(guestChat.dataset.guestEndpoint, { credentials: 'same-origin', headers: { Accept: 'application/json' } });
      if (!response.ok) return;
      const data = await response.json();
      if (guestThread && typeof data.html === 'string' && data.html !== guestHtml) {
        const nearBottom = guestThread.scrollHeight - guestThread.scrollTop - guestThread.clientHeight < 80;
        guestThread.innerHTML = data.html;
        guestHtml = data.html;
        if (nearBottom) guestThread.scrollTop = guestThread.scrollHeight;
      }
    } catch (error) { /* mant�m o conte�do atual */ }
  };
  window.setInterval(refreshGuestChat, 4000);
}
// Bal�o de atendimento do site.
const chatWidget = document.getElementById('chat-widget');
if (chatWidget) {
  const chatBubble = document.getElementById('chat-bubble');
  const chatPanel = document.getElementById('chat-panel');
  const chatClose = document.getElementById('chat-close');
  const chatPresence = chatWidget.querySelector('[data-chat-presence]');
  const chatTitle = chatWidget.querySelector('[data-chat-title]');
  const chatSubtitle = chatWidget.querySelector('[data-chat-subtitle]');
  const chatBadge = chatWidget.querySelector('[data-chat-badge]');
  const chatStart = chatWidget.querySelector('[data-chat-start]');
  const chatStartForm = chatWidget.querySelector('[data-chat-start-form]');
  const chatConversation = chatWidget.querySelector('[data-chat-conversation]');
  const chatThread = chatWidget.querySelector('[data-chat-thread]');
  const chatForm = chatWidget.querySelector('[data-chat-form]');
  const chatCsrf = document.querySelector('meta[name="csrf-token"]');
  const chatToken = chatCsrf ? chatCsrf.content : '';
  let chatOnline = chatWidget.dataset.chatOnline === '1';
  let chatHasSession = false;
  let chatLatestHtml = '';
  let chatLastUnread = null;
  let chatPoll = null;

  const chatRequest = async (url, options = {}) => {
    const response = await fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json', ...(options.headers || {}) }, ...options });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || 'chat-error');
    return data;
  };

  const chatSetStatus = (online, unread = 0) => {
    if (chatLastUnread !== null && unread > chatLastUnread) blPlaySound();
    chatLastUnread = unread;
    chatOnline = Boolean(online);
    if (chatPresence) chatPresence.className = 'chat-presence ' + (chatOnline ? 'is-online' : 'is-offline');
    if (chatTitle) chatTitle.textContent = chatOnline ? 'Atendimento online' : 'Atendimento fora do hor�rio';
    if (chatSubtitle) chatSubtitle.textContent = chatOnline ? 'Fale agora com a equipe.' : 'Deixe sua mensagem; responderemos depois.';
    if (chatBadge) {
      chatBadge.textContent = unread > 99 ? '99+' : String(unread);
      chatBadge.hidden = !unread;
    }
  };

  const chatRender = (data) => {
    chatSetStatus(data.online, data.unread || 0);
    chatHasSession = Boolean(data.session);
    if (data.session) {
      chatStart.hidden = true;
      chatConversation.hidden = false;
    } else if (data.authenticated) {
      chatStart.hidden = false;
      chatConversation.hidden = true;
    } else {
      chatStart.hidden = false;
      chatConversation.hidden = true;
    }
  };

  const chatMessages = async () => {
    try {
      const data = await chatRequest('/chat/mensagens');
      if (chatThread && typeof data.html === 'string' && data.html !== chatLatestHtml) {
        const atBottom = chatThread.scrollHeight - chatThread.scrollTop - chatThread.clientHeight < 90;
        chatThread.innerHTML = data.html;
        chatLatestHtml = data.html;
        if (atBottom || !chatThread.dataset.loaded) chatThread.scrollTop = chatThread.scrollHeight;
        chatThread.dataset.loaded = '1';
      }
      chatSetStatus(chatOnline, data.unread || 0);
      chatStart.hidden = true;
      chatConversation.hidden = false;
      chatHasSession = true;
    } catch (error) {
      if (error.message === 'session') {
        chatHasSession = false;
        chatConversation.hidden = true;
        chatStart.hidden = false;
      }
    }
  };

  const chatLoadStatus = async () => {
    try {
      const data = await chatRequest('/chat/status');
      chatRender(data);
      if (data.session) await chatMessages();
    } catch (error) { /* mant�m o estado atual */ }
  };

  const chatStartSession = async () => {
    if (!chatStartForm) return;
    const button = chatStartForm.querySelector('button[type="submit"]');
    if (button) button.disabled = true;
    try {
      const body = new URLSearchParams(new FormData(chatStartForm));
      body.set('csrf', chatToken);
      await chatRequest('/chat/iniciar', { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body });
      chatStart.hidden = true;
      chatConversation.hidden = false;
      await chatMessages();
    } catch (error) {
      if (chatSubtitle) chatSubtitle.textContent = 'N�o foi poss�vel iniciar o atendimento.';
    } finally {
      if (button) button.disabled = false;
      chatStartForm.dataset.submitting = '';
    }
  };

  const chatSetOpen = (open) => {
    chatPanel.hidden = !open;
    chatBubble.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (open) {
      chatLoadStatus();
      if (!chatPoll) chatPoll = window.setInterval(() => { if (!chatPanel.hidden) chatMessages(); }, 3000);
    } else if (chatPoll) {
      window.clearInterval(chatPoll);
      chatPoll = null;
    }
  };

  chatBubble.addEventListener('click', () => chatSetOpen(chatPanel.hidden));
  chatClose.addEventListener('click', () => { chatSetOpen(false); chatBubble.focus(); });
  if (chatStartForm) chatStartForm.addEventListener('submit', (event) => { event.preventDefault(); chatStartSession(); });
  if (chatForm) chatForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const button = chatForm.querySelector('button[type="submit"]');
    if (button) button.disabled = true;
    try {
      const body = new URLSearchParams(new FormData(chatForm));
      body.set('csrf', chatToken);
      await chatRequest('/chat/mensagem', { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body });
      chatForm.reset();
      await chatMessages();
    } catch (error) {
      if (chatSubtitle) chatSubtitle.textContent = 'N�o foi poss�vel enviar a mensagem.';
    } finally {
      if (button) button.disabled = false;
      chatForm.dataset.submitting = '';
    }
  });
  chatLoadStatus();
  window.setInterval(chatLoadStatus, 30000);
}
// Atualiza a lista de atendimentos do painel enquanto ela estiver aberta.
const adminChatList = document.querySelector('[data-admin-chat-list]');
if (adminChatList) {
  window.setInterval(async () => {
    if (document.hidden) return;
    try {
      const response = await fetch(window.location.href, { credentials: 'same-origin', headers: { Accept: 'text/html' } });
      if (!response.ok) return;
      const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
      const fresh = doc.querySelector('[data-admin-chat-list]');
      if (fresh) adminChatList.innerHTML = fresh.innerHTML;
    } catch (error) { /* mant�m a lista atual */ }
  }, 5000);
}
// Aviso flutuante de novas mensagens para a equipe.
const staffChatAlert = document.getElementById('staff-chat-alert');
if (staffChatAlert) {
  const staffChatBadge = document.getElementById('staff-chat-badge');
  const staffChatToast = document.getElementById('staff-chat-toast');
  const staffChatToastName = document.getElementById('staff-chat-toast-name');
  const staffChatToastBody = document.getElementById('staff-chat-toast-body');
  const staffChatToastLink = document.getElementById('staff-chat-toast-link');
  const staffChatToastClose = document.getElementById('staff-chat-toast-close');
  let staffLastCount = 0;
  let staffLastId = 0;
  let staffDismissedId = 0;

  staffChatToastClose.addEventListener('click', () => {
    staffDismissedId = staffLastId;
    staffChatToast.hidden = true;
  });

  const staffChatPoll = async () => {
    try {
      const response = await fetch(staffChatAlert.dataset.chatAlertEndpoint, { credentials: 'same-origin', headers: { Accept: 'application/json' } });
      if (!response.ok) return;
      const data = await response.json();
      const count = Math.max(0, Number(data.count) || 0);
      staffChatBadge.textContent = count > 99 ? '99+' : String(count);
      staffChatBadge.hidden = count === 0;
      if (count === 0) {
        staffChatToast.hidden = true;
        staffLastCount = 0;
        staffLastId = 0;
        return;
      }
      const latest = data.latest;
      if (!latest) return;
      if (count > staffLastCount || latest.id !== staffLastId) {
        staffLastCount = count;
        staffLastId = latest.id;
        if (latest.id !== staffDismissedId) {
          staffChatToastName.textContent = latest.name || 'Visitante';
          staffChatToastBody.textContent = latest.body || 'Nova mensagem recebida.';
          staffChatToastLink.href = '/admin/atendimento-visitante?guest_id=' + encodeURIComponent(latest.guest_id);
          staffChatToast.hidden = false;
        }
      }
    } catch (error) { /* mant�m o aviso atual */ }
  };
  staffChatPoll();
  window.setInterval(staffChatPoll, 4000);
}
// Atualiza��o autom�tica da conversa aberta.
const liveConversation = document.querySelector('#conversation-view[data-conversation-endpoint]');
if (liveConversation) {
  const liveThread = liveConversation.querySelector('.conversation-thread');
  let liveHtml = liveThread ? liveThread.innerHTML : '';
  let liveLastId = 0;
  const refreshConversation = async () => {
    if (document.hidden) return;
    try {
      const response = await fetch(liveConversation.dataset.conversationEndpoint, { credentials: 'same-origin', headers: { Accept: 'application/json' } });
      if (!response.ok) return;
      const data = await response.json();
      const nextId = Number(data.last_id) || 0;
      if (liveThread && typeof data.html === 'string' && data.html !== liveHtml) {
        const atBottom = liveThread.scrollHeight - liveThread.scrollTop - liveThread.clientHeight < 90;
        liveThread.innerHTML = data.html;
        liveHtml = data.html;
        if (atBottom || !liveThread.dataset.loaded) liveThread.scrollTop = liveThread.scrollHeight;
        liveThread.dataset.loaded = '1';
      }
      if (nextId > liveLastId && liveLastId > 0) blPlaySound();
      liveLastId = nextId;
      if (Number.isFinite(Number(data.unread_client))) updateConversationCounters(data);
      window.dispatchEvent(new Event('conversation:read'));
    } catch (error) { /* mant�m a conversa atual */ }
  };
  refreshConversation();
  window.setInterval(refreshConversation, 4000);
}
// Chat geral da equipe.
const teamChatThread = document.getElementById('team-chat-thread');
if (teamChatThread) {
  let teamChatHtml = teamChatThread.innerHTML;
  const refreshTeamChat = async () => {
    if (document.hidden) return;
    try {
      const response = await fetch(teamChatThread.dataset.teamChatEndpoint, { credentials: 'same-origin', headers: { Accept: 'application/json' } });
      if (!response.ok) return;
      const data = await response.json();
      if (typeof data.html === 'string' && data.html !== teamChatHtml) {
        const atBottom = teamChatThread.scrollHeight - teamChatThread.scrollTop - teamChatThread.clientHeight < 90;
        teamChatThread.innerHTML = data.html;
        teamChatHtml = data.html;
        if (atBottom) teamChatThread.scrollTop = teamChatThread.scrollHeight;
        blPlaySound();
      }
    } catch (error) { /* mant�m o hist�rico atual */ }
  };
  teamChatThread.scrollTop = teamChatThread.scrollHeight;
  window.setInterval(refreshTeamChat, 4000);
}
document.querySelectorAll('.mention-chip').forEach((chip) => {
  chip.addEventListener('click', () => {
    const form = chip.closest('form');
    const textarea = form ? form.querySelector('textarea') : null;
    if (!textarea) return;
    const insert = '@' + chip.dataset.mention + ' ';
    const start = textarea.selectionStart || textarea.value.length;
    const end = textarea.selectionEnd || textarea.value.length;
    textarea.value = textarea.value.slice(0, start) + insert + textarea.value.slice(end);
    textarea.focus();
    textarea.selectionStart = textarea.selectionEnd = start + insert.length;
  });
});

// === Modal: criar tarefa a partir de mensagem interna ===
(function () {
  const taskDialog = document.createElement('dialog');
  taskDialog.className = 'task-modal-dialog';
  const overlay = document.createElement('div');
  overlay.className = 'task-modal-overlay';
  overlay.hidden = true;
  overlay.innerHTML = '<div class="task-modal" role="dialog" aria-modal="true" aria-labelledby="task-modal-title">' +
    '<div class="task-modal-head"><h2 id="task-modal-title">Nova tarefa</h2><button type="button" class="task-modal-close" aria-label="Fechar">×</button></div>' +
    '<form method="post" action="/admin/tarefa" class="task-modal-form">' +
    '<input type="hidden" name="csrf" value="">' +
    '<input type="hidden" name="source_message_id" value="">' +
    '<input type="hidden" name="client_id" value="">' +
    '<input type="hidden" name="case_id" value="">' +
    '<label>Título<input type="text" name="title" required maxlength="180"></label>' +
    '<label>Descrição<textarea name="description" rows="3"></textarea></label>' +
    '<label>Data (opcional)<input type="date" name="due_date"></label>' +
    '<label>Hora (opcional)<input type="time" name="due_time"></label>' +
    '<label>Prioridade<select name="priority"><option value="normal">Normal</option><option value="alta">Alta</option><option value="urgente">Urgente</option></select></label>' +
    '<div class="task-modal-actions"><button type="submit" class="btn">Criar tarefa</button><button type="button" class="btn ghost task-modal-cancel">Cancelar</button></div>' +
    '</form></div>';
  taskDialog.appendChild(overlay);
  document.body.appendChild(taskDialog);
  const form = overlay.querySelector('form');
  const close = () => {
    overlay.hidden = true;
    if (taskDialog.open) taskDialog.close();
    document.body.style.overflow = '';
  };
  // Delegação: sobrevive à atualização automática do histórico de mensagens.
  document.addEventListener('click', (event) => {
    const button = event.target.closest('[data-task-from-message]');
    if (!button) return;
    const token = (document.querySelector('meta[name="csrf-token"]') || {}).content || '';
    form.querySelector('[name=csrf]').value = token;
    form.querySelector('[name=source_message_id]').value = button.dataset.taskFromMessage;
    form.querySelector('[name=client_id]').value = button.dataset.taskClient || '';
    form.querySelector('[name=case_id]').value = button.dataset.taskCase || '';
    form.querySelector('[name=title]').value = (button.dataset.taskBody || '').slice(0, 120);
    form.querySelector('[name=description]').value = button.dataset.taskBody || '';
    overlay.hidden = false;
    if (typeof taskDialog.showModal === 'function' && !taskDialog.open) taskDialog.showModal();
    else taskDialog.setAttribute('open', '');
    document.body.style.overflow = 'hidden';
    form.querySelector('[name=title]').focus();
  });
  overlay.querySelector('.task-modal-close').addEventListener('click', close);
  overlay.querySelector('.task-modal-cancel').addEventListener('click', close);
  overlay.addEventListener('click', (event) => { if (event.target === overlay) close(); });
  taskDialog.addEventListener('cancel', (event) => { event.preventDefault(); close(); });
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape' && !overlay.hidden) close(); });
})();

document.querySelectorAll('input[type="datetime-local"], input[type="date"]').forEach((input) => {
  if (input.dataset.pickerReady === '1') return;
  input.dataset.pickerReady = '1';
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'datetime-picker-btn';
  button.textContent = 'Selecionar no calend\u00e1rio';
  button.setAttribute('aria-label', 'Abrir calend\u00e1rio para escolher data e hora');
  button.addEventListener('click', () => {
    try {
      if (typeof input.showPicker === 'function') input.showPicker();
      else { input.focus(); input.click(); }
    } catch (error) { input.focus(); }
  });
  input.insertAdjacentElement('afterend', button);
});

document.querySelectorAll('[data-calendar-date]').forEach((cell) => {
  if (cell.dataset.calendarReady === '1') return;
  cell.dataset.calendarReady = '1';
  cell.addEventListener('click', (event) => {
    if (event.target.closest('a,button,details,summary')) return;
    window.location.href = '/admin/compromissos?novo=1&data=' + encodeURIComponent(cell.dataset.calendarDate);
  });
});

document.querySelectorAll('form[action="/admin/conteudos/excluir"]').forEach((form) => {
  form.addEventListener('submit', (event) => {
    if (!window.confirm('Excluir definitivamente este conte?do?')) event.preventDefault();
  });
});
