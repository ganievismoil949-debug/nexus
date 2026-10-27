/* Local UI: no cloud endpoints or third-party scripts. */
(() => {
  'use strict';
  const root=document.getElementById('nexus-shell');
  const token=document.querySelector('meta[name="nexus-token"]').content;
  const $=id=>document.getElementById(id);
  let busy=false,listening=false,voicePreview=false,currentJob=null,status={},toastTimer,collapseTimer,moodTimer,listenSequence=0;
  async function api(path,body){
    const response=await fetch('/api/'+path,{method:body===undefined?'GET':'POST',headers:{'X-Nexus-Token':token,...(body===undefined?{}:{'Content-Type':'application/json'})},body:body===undefined?undefined:JSON.stringify(body)});
    const result=await response.json();
    if(!response.ok)throw new Error(result.error||'Request failed.');
    return result;
  }
  function toast(text){$('toast').textContent=text;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,6500);}
  function mood(value){
    clearTimeout(moodTimer);
    root.querySelector('[data-panel="home"]').dataset.mood=value;
    const headings={idle:['Right here with you.','A familiar face. A helping hand.'],listening:["I'm all ears.",'Take your time. I’m listening.'],thinking:['A moment to think.','Working through your request, right here.'],speaking:['Here’s what I found.','A little help, in my own voice.'],happy:['Right here with you.','Ready for whatever comes next.']};
    const words=headings[value]||headings.idle;
    $('home-heading').textContent=words[0];$('home-subtitle').textContent=words[1];
    if(value==='happy')moodTimer=setTimeout(()=>mood('idle'),1900);
  }
  function avatar(){const box=document.createElement('span');box.className='n-avatar';box.setAttribute('aria-hidden','true');const img=document.createElement('img');img.src='/icon.svg';img.alt='';box.append(img);return box;}
  function pending(text){
    let row=$('pending-message');
    if(!row){row=document.createElement('div');row.id='pending-message';row.className='n-message assistant n-pending';const content=document.createElement('div');const author=document.createElement('span');author.className='n-author';author.textContent='Nexus';const line=document.createElement('p');line.id='pending-text';content.append(author,line);row.append(avatar(),content);$('messages').append(row);}
    $('pending-text').textContent=text;
  }
  function setBusy(value){
    busy=value;const active=value||listening||voicePreview;root.dataset.busy=String(active);
    $('send-button').disabled=active;$('new-chat').disabled=active;$('talk-button').disabled=active;$('test-voice').disabled=active;$('stop-button').disabled=!active;
    root.querySelectorAll('[data-quick]').forEach(b=>b.disabled=active);
    if(value)pending('Thinking locally…');else $('pending-message')?.remove();
  }
  root.dataset.visible=String(!document.hidden);
  document.addEventListener('visibilitychange',()=>{root.dataset.visible=String(!document.hidden);});
  $('companion-button').addEventListener('click',()=>{if(busy||listening||voicePreview)return;mood('happy');$('home-heading').textContent='Hello, you.';$('home-subtitle').textContent='It’s good to have you here.';});
  function page(name){
    root.dataset.activePage=name;
    root.querySelectorAll('[data-panel]').forEach(el=>el.hidden=el.dataset.panel!==name);
    root.querySelectorAll('[data-page]').forEach(el=>{if(el.dataset.page===name)el.setAttribute('aria-current','page');else el.removeAttribute('aria-current');});
    $('page-title').textContent=name[0].toUpperCase()+name.slice(1);
    if(name==='memory')loadMemory().catch(e=>toast(e.message));
    if(name==='settings'){refresh().catch(e=>toast(e.message));loadActivity().catch(e=>toast(e.message));}
    if(name==='chat')$('chat-input').focus();
  }
  function collapse(value){root.dataset.collapsed=String(value);$('sidebar-toggle').setAttribute('aria-expanded',String(!value));$('sidebar-toggle').setAttribute('aria-label',value?'Expand sidebar':'Collapse sidebar');$('sidebar-toggle').title=value?'Expand sidebar':'Collapse sidebar';}
  $('sidebar-toggle').addEventListener('click',()=>{collapse(root.dataset.collapsed!=='true');clearTimeout(collapseTimer);collapseTimer=setTimeout(()=>api('settings',{collapsed:root.dataset.collapsed==='true'}).catch(e=>toast(e.message)),250);});
  root.querySelectorAll('[data-page]').forEach(button=>button.addEventListener('click',()=>page(button.dataset.page)));
  function message(role,text,animate=true){
    const row=document.createElement('div');row.className='n-message '+(role==='user'?'user':'assistant')+(animate?'':' n-restored');if(role!=='user')row.append(avatar());
    const content=document.createElement('div');const author=document.createElement('span');author.className='n-author';author.textContent=role==='user'?'You':'Nexus';
    const p=document.createElement('p');p.textContent=text;content.append(author,p);row.append(content);$('messages').insertBefore(row,$('pending-message'));$('messages').scrollTop=$('messages').scrollHeight;
  }
  async function loadHistory(){const history=await api('history');$('messages').replaceChildren();if(!history.length)message('assistant',"I'm here. What would you like to do?");else history.forEach(m=>message(m.role,m.content,false));}
  async function refresh(initial=false){
    status=await api('status');
    $('engine-status').textContent=status.ready?'Local AI · '+status.resolved_model+(status.model==='auto'?' · Auto':''):'Local AI unavailable · Check Settings';
    $('voice-name').textContent=status.voice.speech;
    $('auto-speak').checked=status.auto_speak;$('animation').checked=status.animation;root.dataset.motion=status.animation?'on':'off';
    $('gmail-status').textContent=status.gmail||'Not connected';$('telegram-status').textContent=status.telegram?'Connected':'Not connected';
    $('capabilities').textContent=(status.voice.recognition?'Offline listening ready. ':'Offline listening needs setup.sh. ')+'Desktop session: '+status.session+'. Accessibility support depends on each application.';
    const select=$('model-select');select.replaceChildren();
    if(!status.models.length){const o=new Option('Start Ollama first','');select.add(o);$('model-hint').textContent='Install Ollama and one local model to begin.';}
    else {
      select.add(new Option(status.recommended_model?'Automatic · '+status.recommended_model:'Automatic · no model fits current memory','auto',false,status.model==='auto'));
      status.models.forEach(model=>{
        const labels={'qwen2.5:1.5b':'Qwen 2.5 1.5B · compact','qwen3:0.6b':'Qwen 3 0.6B','qwen3.5:0.8b':'Qwen 3.5 0.8B','qwen3.5:2b-q4_K_M':'Qwen 3.5 2B Q4 · balanced','qwen3.5:4b-q4_K_M':'Qwen 3.5 4B Q4 · higher memory','qwen3.5:2b':'Qwen 3.5 2B','qwen3.5:4b':'Qwen 3.5 4B · higher memory'};
        const title=(labels[model]||model)+(model===status.recommended_model?' · recommended':'');
        select.add(new Option(title,model,false,model===status.model));
      });
      $('model-hint').textContent=status.recommended_model
        ? 'Auto chooses an installed model within available memory. Current choice: '+status.recommended_model+'. Speed depends on your computer and request.'
        : status.model!=='auto'&&!status.resolved_model
          ? 'The selected model is unavailable. Choose Automatic or an installed model.'
          : 'No installed model currently fits available memory. Close other apps or choose a smaller local model.';
    }
    if(initial){collapse(status.collapsed);if(status.busy){currentJob=status.busy;setBusy(true);poll(currentJob);}}
  }
  async function poll(identity){
    try{
      const job=await api('jobs/'+identity);
      if(currentJob!==identity)return;
      if(job.done){setBusy(false);currentJob=null;mood(job.error?'idle':'happy');const seconds=(Math.max(0,job.elapsed_ms||0)/1000).toFixed((job.elapsed_ms||0)<10000?1:0);$('chat-status').textContent=job.engine==='model'?'Answered with '+(job.model||'local AI')+' in '+seconds+'s · saved on this computer.':'Completed locally in '+seconds+'s.';$('home-status').textContent='Ready when you are.';$('home-answer').textContent=job.answer;message('assistant',job.answer);if(job.voice_error)toast(job.voice_error);return;}
      const label=job.stage==='speaking'?'Speaking…':job.stage==='working'?'Working: '+(job.current_action||'your request'):'Thinking locally…';
      mood(job.stage==='speaking'?'speaking':'thinking');if(job.stage==='speaking')$('home-answer').textContent=job.answer;$('chat-status').textContent=label;$('home-status').textContent=label;pending(label);
      setTimeout(()=>poll(identity),document.hidden?1600:700);
    }catch(e){setBusy(false);currentJob=null;mood('idle');toast(e.message);}
  }
  async function send(text){
    if(busy||listening||voicePreview||!text.trim())return;
    setBusy(true);mood('thinking');$('home-answer').textContent='';$('home-status').textContent='Thinking locally…';$('chat-status').textContent='Thinking locally…';
    try{const result=await api('chat',{text:text.trim()});message('user',text.trim());$('chat-input').value='';currentJob=result.job;poll(result.job);}
    catch(e){setBusy(false);mood('idle');toast(e.message);}
  }
  $('chat-form').addEventListener('submit',event=>{event.preventDefault();send($('chat-input').value);});
  $('chat-input').addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();send(event.target.value);}});
  root.querySelectorAll('[data-quick]').forEach(button=>button.addEventListener('click',()=>send(button.dataset.quick)));
  $('new-chat').addEventListener('click',async()=>{try{await api('new-chat',{});await loadHistory();$('home-answer').textContent='';}catch(e){toast(e.message);}});
  $('stop-button').addEventListener('click',async()=>{listenSequence++;try{await api('stop',{});mood('idle');$('home-status').textContent='Stopping. Completed actions remain in Activity.';$('chat-status').textContent='Stopping before the next action…';}catch(e){toast(e.message);}});
  document.addEventListener('keydown',event=>{if(event.key==='Escape'&&(busy||listening||voicePreview)){event.preventDefault();$('stop-button').click();}});
  $('talk-button').addEventListener('click',async()=>{
    if(listening||busy||voicePreview)return;
    if(!status.voice?.recognition){page('settings');toast('Run setup.sh once to install offline speech recognition.');return;}
    listening=true;const sequence=++listenSequence;setBusy(false);mood('listening');$('talk-label').textContent='Listening…';$('home-status').textContent='Speak now. Listening for up to 8 seconds.';
    try{const result=await api('voice/listen',{});if(sequence!==listenSequence)return;listening=false;setBusy(false);mood('idle');if(result.text){$('home-status').textContent='You said: '+result.text;await send(result.text);}else toast('I did not catch that. Please try again.');}
    catch(e){mood('idle');toast(e.message);}
    finally{listening=false;$('talk-label').textContent='Talk to Nexus';setBusy(busy);}
  });
  async function loadMemory(){
    const memories=await api('memories');$('memory-list').replaceChildren();
    if(!memories.length)$('memory-feedback').textContent='No saved preferences yet. Tell Nexus what to remember.';
    else $('memory-feedback').textContent=memories.length+' saved preferences.';
    memories.forEach(item=>{const row=document.createElement('div');row.className='n-saved';const text=document.createElement('div');text.textContent=item.text;const remove=document.createElement('button');remove.className='n-button';remove.textContent='Forget';remove.addEventListener('click',async()=>{try{await api('forget',{id:item.id});await loadMemory();}catch(e){toast(e.message);}});row.append(text,remove);$('memory-list').append(row);});
  }
  $('memory-form').addEventListener('submit',async event=>{event.preventDefault();try{await api('memory',{text:$('memory-input').value});$('memory-input').value='';await loadMemory();}catch(e){toast(e.message);}});
  for(const [id,key] of [['auto-speak','auto_speak'],['animation','animation']])$(id).addEventListener('change',async event=>{try{await api('settings',{[key]:event.target.checked});if(key==='animation')root.dataset.motion=event.target.checked?'on':'off';}catch(e){toast(e.message);}});
  $('model-select').addEventListener('change',async event=>{try{await api('settings',{model:event.target.value});await refresh();toast('Local model updated.');}catch(e){toast(e.message);}});
  $('test-voice').addEventListener('click',async()=>{if(busy||listening||voicePreview)return;voicePreview=true;setBusy(false);mood('speaking');try{await api('voice/test',{});toast('Voice test finished.');}catch(e){toast(e.message);}finally{voicePreview=false;setBusy(false);mood('idle');}});
  async function loadActivity(){const items=await api('activity');$('activity-list').replaceChildren();if(!items.length){const p=document.createElement('p');p.className='n-small';p.textContent='No actions yet.';$('activity-list').append(p);}items.forEach(item=>{const row=document.createElement('div');row.className='n-activity';const title=document.createElement('strong');title.textContent=item.tool+' · '+new Date(item.created*1000).toLocaleTimeString();const result=document.createElement('pre');try{result.textContent=JSON.stringify(JSON.parse(item.result),null,2);}catch{result.textContent=item.result;}row.append(title,result);$('activity-list').append(row);});}
  $('refresh-activity').addEventListener('click',()=>loadActivity().catch(e=>toast(e.message)));
  function values(form){return Object.fromEntries(new FormData(form).entries());}
  async function formCall(form,route){const submit=form.querySelector('button[type="submit"]');submit.disabled=true;$('account-feedback').textContent='Connecting…';try{return await api(route,values(form));}finally{submit.disabled=false;form.querySelectorAll('input[type="password"]').forEach(input=>input.value='');}}
  $('gmail-form').addEventListener('submit',async event=>{event.preventDefault();try{const r=await formCall(event.target,'connect/gmail');$('account-feedback').textContent='Gmail connected. Credentials stored in '+r.storage+'.';await refresh();}catch(e){$('account-feedback').textContent=e.message;}});
  $('telegram-form').addEventListener('submit',async event=>{event.preventDefault();try{const r=await formCall(event.target,'connect/telegram');$('telegram-code-form').hidden=!!r.connected;$('account-feedback').textContent=r.connected?'Telegram connected.':'Enter the code Telegram sent you.';if(r.connected)await refresh();}catch(e){$('account-feedback').textContent=e.message;}});
  $('telegram-code-form').addEventListener('submit',async event=>{event.preventDefault();try{const r=await formCall(event.target,'connect/telegram/verify');$('telegram-2fa').hidden=!r.needs_password;$('account-feedback').textContent=r.needs_password?'Enter your Telegram two-step verification password.':'Telegram connected.';if(r.connected){event.target.reset();event.target.hidden=true;await refresh();}}catch(e){$('account-feedback').textContent=e.message;}});
  root.querySelectorAll('[data-disconnect]').forEach(button=>button.addEventListener('click',async()=>{try{await api('disconnect',{service:button.dataset.disconnect});await refresh();toast('Account disconnected.');}catch(e){toast(e.message);}}));
  Promise.all([refresh(true),loadHistory()]).catch(e=>toast('Nexus could not connect: '+e.message));
})();
