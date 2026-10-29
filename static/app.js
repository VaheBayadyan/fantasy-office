const $ = (selector) => document.querySelector(selector);
const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const el = (tag, className, text) => { const node = document.createElement(tag); node.className = className; node.textContent = text; return node; };

function renderLeague(league, index) {
  const card = el('article', 'league-card', '');
  if (league.error) {
    card.innerHTML = `<div class="league-head"><div><div class="section-kicker">LEAGUE ${String(index + 1).padStart(2,'0')}</div><h2 class="league-title">${escapeHtml(league.name)}</h2><p class="league-sub">${escapeHtml(league.error)}</p></div></div>`;
    return card;
  }
  const current = league.current;
  const next = league.next;
  const categories = league.categories || [];
  const rows = categories.map(cat => `<tr><td class="category-name">${escapeHtml(cat.name)}</td><td>${escapeHtml(cat.mine ?? '—')}</td><td>${escapeHtml(cat.theirs ?? '—')}</td><td><span class="result ${escapeHtml(cat.result || 'pending')}">${escapeHtml((cat.result || 'pending').toUpperCase())}</span></td></tr>`).join('');
  const agents = (league.suggestions || []).map(group => `<div class="agent-category"><h4>${escapeHtml(group.category)} · AVAILABLE</h4>${group.players.map(player => `<div class="agent"><div><span class="agent-name">${escapeHtml(player.name)}</span><div class="agent-meta">${escapeHtml(player.team)} · ${escapeHtml(player.positions)}</div></div><span class="agent-value">${escapeHtml(player.value)}</span></div>`).join('')}</div>`).join('');
  const nextProfile = (league.next_categories || []).length ? `<div class="season-profile"><div class="mini-label">NEXT OPPONENT · SEASON PROFILE</div>${league.next_categories.filter(cat => cat.result === 'losing').slice(0, 4).map(cat => `<div class="profile-row"><span>${escapeHtml(cat.name)}</span><span>${escapeHtml(cat.mine)} <b>vs</b> ${escapeHtml(cat.theirs)}</span></div>`).join('') || '<div class="profile-row">No season category deficits found.</div>'}<p class="note">Your total vs their total. A directional scouting view, not a matchup forecast.</p></div>` : '';
  card.innerHTML = `<div class="league-head"><div><div class="section-kicker">LEAGUE ${String(index + 1).padStart(2,'0')} / ${escapeHtml(league.scoring || 'BASKETBALL')}</div><h2 class="league-title">${escapeHtml(league.name)}</h2><div class="league-sub">${escapeHtml(league.team)}</div></div><span class="week-pill">WEEK ${escapeHtml(league.week)}</span></div><div class="league-body"><div class="matchup"><h3 class="section-heading">This week's matchup</h3><p class="section-desc">Live Yahoo category totals</p>${current ? `<div class="versus"><strong>${escapeHtml(current.mine.name)}</strong><span>VS</span><strong>${escapeHtml(current.opponent.name)}</strong></div><table class="category-table"><thead><tr><th>CATEGORY</th><th>YOU</th><th>THEM</th><th>EDGE</th></tr></thead><tbody>${rows}</tbody></table>` : '<p class="section-desc">No head-to-head matchup found for this week.</p>'}</div><aside class="side"><h3 class="section-heading">Looking ahead</h3><p class="section-desc">Your next scheduled opponent</p><div class="next-box"><div class="mini-label">${next ? `WEEK ${escapeHtml(next.week || Number(league.week)+1)} OPPONENT` : 'NEXT OPPONENT'}</div><div class="next-name">${escapeHtml(next?.opponent?.name || 'Schedule not available yet')}</div><div class="next-sub">${next ? 'Plan your category approach before the week starts.' : 'Check again when Yahoo publishes the next matchup.'}</div></div>${nextProfile}<h3 class="section-heading">Free-agent radar</h3><p class="section-desc">Season leaders in categories you trail or tie</p><div class="agent-list">${agents || '<span class="section-desc">No target categories to show yet.</span>'}</div><p class="note">Season totals are scouting signals. Check games remaining, injuries, and roster slots before adding anyone.</p></aside></div>`;
  return card;
}

async function load() {
  $('#refresh').disabled = true;
  $('#status').className = 'status';
  $('#status').textContent = 'Loading Yahoo matchups…';
  $('#overview').hidden = true;
  $('#leagues').replaceChildren();
  try {
    const response = await fetch('/api/dashboard', {cache:'no-store'});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Yahoo request failed.');
    if (!data.connected) {
      $('#status').innerHTML = data.configured ? 'Connect your Yahoo account to see your leagues. <a href="/auth/start">Connect Yahoo →</a>' : 'Set your Yahoo app credentials to begin. See the README for the two-minute setup.';
      return;
    }
    const leagues = data.leagues || [];
    const active = leagues.filter(league => !league.error);
    const edges = active.reduce((sum, league) => sum + (league.categories || []).filter(cat => cat.result === 'winning').length, 0);
    const targets = active.reduce((sum, league) => sum + (league.categories || []).filter(cat => cat.result === 'losing' || cat.result === 'tied').length, 0);
    $('#overview').innerHTML = `<div class="stat-card"><span class="card-label">ACTIVE LEAGUES</span><div class="stat-number">${leagues.length.toString().padStart(2,'0')}</div></div><div class="stat-card"><span class="card-label">CATEGORY EDGES</span><div class="stat-number">${edges.toString().padStart(2,'0')} <span>this week</span></div></div><div class="stat-card"><span class="card-label">CATEGORIES TO TARGET</span><div class="stat-number">${targets.toString().padStart(2,'0')} <span>this week</span></div></div>`;
    $('#overview').hidden = false;
    leagues.forEach((league, index) => $('#leagues').append(renderLeague(league, index)));
    $('#status').textContent = leagues.length ? '' : 'No current Yahoo Fantasy Basketball teams were found for this account.';
  } catch (error) {
    $('#status').className = 'status error';
    $('#status').textContent = error.message;
  } finally {
    $('#refresh').disabled = false;
  }
}

const error = new URLSearchParams(location.search).get('error');
if (error) { $('#status').className = 'status error'; $('#status').textContent = error; history.replaceState(null, '', '/'); }
$('#refresh').addEventListener('click', load);
if (!error) load();
