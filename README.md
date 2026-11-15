# Bomfim & Lacerda Advocacia — ambiente de testes

Aplicação funcional local de referência, **não homologada para produção**. Site público, área individual do cliente e administração compartilham o mesmo banco, com suporte a **SQLite local** e **PostgreSQL em produção**. Não usar dados reais.

## Iniciar

Requer Python 3.12+ e Flask 3.x. No terminal, dentro da pasta do projeto:

```bash
python -m pip install -r requirements.txt
python create_admin.py
python app.py
```

O `app.py` inicia o projeto pelo adaptador Flask (`flask_app.py`). Para usar um servidor WSGI, aponte-o para `wsgi:application`. O servidor HTTP anterior permanece apenas como compatibilidade interna da suíte de testes.

Abra `http://127.0.0.1:8080`. O comando `create_admin.py` cria uma conta de **super administrador**. Execute uma vez para **Edleusa Pessoa** e outra para **Rozária Neta Bomfim Lacerda**, usando e-mails temporários (por exemplo `edleusa.admin@bomfimlacerda.test` e `rozaria.admin@bomfimlacerda.test`). As senhas são definidas na hora, com no mínimo 12 caracteres. Quando houver e-mail oficial, troque-o em **Usuários** no painel. Use somente dados fictícios.

## Arquivos locais (fora do GitHub)

A pasta `local_only/` reúne o que é usado apenas no desenvolvimento local: suíte de testes, referências visuais, `codigo.docx`, `run_dev.ps1`, `migrate_sqlite_to_postgres.py` e o `.env.example`. Ela está no `.gitignore` e não será enviada ao GitHub. O banco SQLite, uploads e backups em `private/` e o arquivo `.env` também são ignorados.

## Banco de dados

A aplicação lê o arquivo `.env` automaticamente e escolhe o banco por `DATABASE_URL`:

```text
# SQLite local, usando os dados existentes
DATABASE_URL=sqlite:///private/app.db

# PostgreSQL em produção
DATABASE_URL=postgresql://usuario:senha@host:5432/banco?sslmode=require
```

O SQLite local continua sendo o padrão e não precisa de Docker. Se `DATABASE_URL` não existir, a aplicação usa `APP_DB` ou `private/app.db`. O mesmo código roda nos dois bancos; a camada de compatibilidade fica em `db_compat.py`.

Para iniciar localmente:

```powershell
python app.py
```

Também é possível usar o atalho local:

```powershell
.\local_only\run_dev.ps1
```

Em produção, defina `DATABASE_URL` nas variáveis de ambiente do servidor com as credenciais reais do PostgreSQL. Não grave essa URL no repositório.

O script de migração abaixo é opcional e serve apenas para copiar dados de um SQLite para um PostgreSQL de teste; não é necessário para iniciar em produção:

```powershell
python local_only\migrate_sqlite_to_postgres.py --replace
```

## Acesso por outro computador na rede

Por padrão, o Flask agora escuta em `0.0.0.0:8080`, permitindo acesso pela rede local. Ao iniciar com `python app.py`, o terminal exibe o endereço local e o IP de rede.

No outro computador, abra:

```text
http://IP-DO-COMPUTADOR:8080
```

Descubra o IPv4 no Windows com:

```powershell
Get-NetIPAddress -AddressFamily IPv4 |
  Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } |
  Select-Object InterfaceAlias,IPAddress
```

Se a conexão não abrir, libere a porta no firewall do Windows. Execute o PowerShell **como Administrador**:

```powershell
New-NetFirewallRule -DisplayName "Bomfim Lacerda 8080" `
  -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow -Profile Private
```

Os dois computadores precisam estar na mesma rede. Este é um ambiente de testes sem HTTPS; não exponha a aplicação à Internet nem use dados reais. Para alterar porta ou interface:

```powershell
$env:PORT = "8081"
$env:HOST = "0.0.0.0"
python app.py
```

## Testes

```bash
python -m unittest discover -s local_only\tests -t . -v
```

A suíte usa banco SQLite e uploads temporários, mesmo que `DATABASE_URL` esteja definida, e sobe o servidor em porta aleatória. Ela cobre autenticação, permissões, casos, documentos, notificações, conversas por assunto, leitura individual, encerramento e histórico, entre outros fluxos.

## Migrações e backup

Antes de alterações estruturais, mantenha uma cópia dos arquivos e do banco em `private/backups/`. A migração para o schema 21 também cria automaticamente um backup do banco antes de aplicar as novas estruturas de clientes internos, portal do cliente, agenda com privacidade e participantes, tarefas, documentos internos, comunicação interna, anexos de conversas, atendimento de visitantes e chat flutuante.

O banco possui controle de versão em `schema_migrations`. Antes de aplicar uma migração estrutural em um banco existente, o sistema cria um backup em `private/backups/` (banco via API de backup do SQLite) e um ZIP dos uploads. A versão atual do schema é 21. Na migração das conversas, as mensagens anteriores são preservadas como **histórico anterior**, agrupadas por cliente, caso e visibilidade. Na migração da fila de contatos, os registros antigos ficam como **não classificados**, pois não é possível presumir se já foram respondidos.

## Estado da evolução

- **Etapa 0 concluída**: backup automático antes de migração e controle de versão do schema.
- **Etapa 1 (núcleo) concluída**: permissões individuais, clientes por advogado, telefone/proprietário, configurações administrativas e proteção de super admins.
- **Etapa 2 concluída**: status com cores (vermelho/amarelo/azul/verde/cinza), alertas de mensagens não lidas e de inatividade, central de notificações no cabeçalho, contador, notificações no navegador (mediante permissão) e deduplicação.
- **Etapa 3 concluída**: cliente abre novo atendimento informando assunto/descrição; o caso é criado em fila sem responsável; administrador distribui para um advogado; título original preservado; histórico de renomeações, status e atribuições em `case_events`; página de histórico administrativo e detalhe do atendimento para o cliente.
- **Etapa 4 concluída**: painel administrativo reformulado como central de gestão, com indicadores, busca, mensagens/solicitações recentes e menus próprios. O advogado tem painel individual em `/advogado`; a consulta de casos foi ampliada posteriormente para todos os advogados.
- **Etapa 5 concluída**: área do cliente reformulada como **Meu Espaço**, com layout próprio, menu lateral, indicadores coloridos, atendimentos, mensagens, documentos, compromissos, atualizações, novo atendimento, perfil e **pendências do cliente** com upload direto de documentos e análise do escritório.
- **Etapa 6 concluída**: status documental completo (aguardando análise, analisado, aceito, complementação e disponibilizado) com página de análise do escritório; status de compromissos (pendente, realizado, cancelado); lembretes automáticos de compromissos; notificações consolidadas para documentos, pendências e compromissos.
- **Etapa 7 concluída**: lixeira com restauração e exclusão definitiva (clientes, casos e documentos), filtros e exportação CSV da auditoria, relatórios com período, produtividade por responsável e tempo médio de resposta, além da aplicação das permissões nas principais rotas de casos, mensagens, documentos, pendências e relatórios.
- **Etapa 8 concluída (MFA)**: autenticação em duas etapas por TOTP para super admins, com chave manual/otpauth, confirmação por código, códigos de recuperação hasheados e exibidos uma única vez, redefinição de MFA por outro super admin, auditoria de ativação/desativação/recuperação e prevenção de reutilização do mesmo código TOTP. O MFA é opcional e pode ser ativado em `/admin/seguranca`.
- **Etapa 9 concluída (LGPD — exportação)**: o cliente baixa os próprios dados em JSON na área “Meu perfil”; o super admin exporta os dados de qualquer cliente em `/admin/clientes`. O arquivo inclui perfil, casos, documentos, mensagens visíveis ao cliente, compromissos, atualizações, solicitações, pendências, eventos visíveis e notificações, excluindo relatos internos, senhas e metadados de armazenamento.
- **Conversas e consulta de casos**: cada assunto tem uma conversa com leitura por usuário; somente a equipe autorizada encerra, o histórico fica consultável e um novo contato inicia outra conversa. Advogados podem consultar todos os casos ativos e seus documentos, mas a edição e o envio continuam sujeitos às permissões e atribuições existentes.
- **Área administrativa organizada**: indicadores levam a listas filtradas; fichas reúnem dados e ações no contexto; clientes, casos, conversas, documentos, pendências, solicitações, agenda e usuários têm filtros e paginação. A alteração de um responsável principal preserva os demais profissionais vinculados.
- **Chat flutuante e atendimento de visitantes**: um balão fixo no canto da tela atende visitantes e clientes logados; o status online depende de haver administrador, advogado ou funcionário com sessão ativa. Sem equipe online, o balão continua aceitando mensagens para resposta posterior. A equipe acessa `/admin/chats`, responde em `/admin/atendimento-visitante` e o visitante acompanha por `/atendimento/<token>`. A fila de contatos continua disponível como visão de CRM. O envio automático de e-mail segue pendente de SMTP; a atualização usa polling de 3–5 segundos, não WebSocket.
- **Chat dos atendimentos**: conversas de cliente e equipe usam balões (cliente à esquerda, escritório à direita), resposta fixa com anexo, atualização automática a cada 4 segundos, contador com pulsação, aviso clicável e som opcional no navegador.
- **Painéis modernizados (etapa visual)**: administração, advogados, funcionários e clientes passaram a usar menu lateral azul-marinho com item ativo dourado, topo com notificações e identificação do usuário, cartões de indicadores, painel de atenção, atendimentos prioritários, agenda, acompanhamento e acesso rápido. O site público permanece com o cabeçalho institucional.
- **Advogado x funcionário**: o schema 10 adiciona `users.staff_kind` (`lawyer` ou `employee`), mantendo `role='staff'`. Advogados continuam podendo consultar todos os casos ativos; funcionários ficam restritos aos clientes/casos atribuídos, às conversas desse escopo e não acessam relatórios sem permissão explícita.
- **Clientes internos e ficha ampliada (schema 21)**: é possível cadastrar cliente para controle interno sem e-mail/senha de portal; o acesso pode ser habilitado depois com validação de identidade e vínculo ao mesmo cadastro. A ficha do cliente permite cadastrar e organizar múltiplos casos e reúne comunicação com o cliente, comunicação interna, agenda, tarefas, pendências e documentos.
- **Agenda colaborativa (schema 21)**: eventos com ou sem cliente, título livre, tipo, privacidade (pessoal privado, interno ou cliente), responsável, participantes, local, lembretes de 1 hora/1 dia, edição, cancelamento, exclusão lógica e histórico. Eventos pessoais são privados inclusive para a administradora geral.
- **Comunicação interna por caso (schema 21)**: mensagens internas separadas das conversas com clientes, com autores, histórico, anexos, notificações e acesso restrito à equipe autorizada do caso. A interface reutiliza o chat em tempo real, com menções @nome, notificações direcionadas e conversão de mensagens em tarefas vinculadas ao caso.
- **Perfis e menus (schema 21)**: todos os usuários podem personalizar foto e capa, com restauração para o padrão institucional. Os painéis usam submenus expansíveis (Atendimento ao cliente, Comunicação interna, Agenda e Gestão, Documentos, Gestão do site e Configurações); o Super Admin alterna entre visão geral do escritório e sua rotina individual.
- **Chat geral da equipe (schema 21)**: canal interno independente de clientes/casos, com menções @nome, anexos, contador de não lidas, atualização automática e notificações direcionadas. Fica separado do chat do site e das conversas de clientes.
- **Tarefas colaborativas (schema 21)**: tarefas com responsável, colaboradores, subtarefas, prioridade, prazo e vínculos opcionais com clientes, casos, documentos e mensagens internas. A conversão de mensagem interna em tarefa preserva o caso e a mensagem de origem.
- **FAQ categorizado (schema 21)**: quatro categorias oficiais, perguntas expansíveis, edição, ordenação, publicação/despublicação e CTA de contato. Aviso permanente “ATENÇÃO AOS GOLPES!” no FAQ, na página de contato e na Área do Cliente.
- **Notificações direcionadas**: links para conversa, tarefa, compromisso, documento, solicitação ou pendência específicos; ao abrir, apenas a notificação acessada é marcada como lida.
- **Agenda, tarefas, documentos internos e conversas**: tarefas/prazos têm criação, edição, atribuição, prioridade, conclusão, exclusão lógica, histórico de auditoria e destaque de atrasos; documentos internos têm upload, edição de metadados, visibilidade por equipe/caso, download privado, remoção lógica e histórico; as conversas usam chat em tempo real com balões, resposta fixa, anexos, notificações visuais, contador pulsante e som opcional.
- **Próxima etapa**: anonimização/retenção LGPD, envio de e-mail/SMTP, MFA obrigatório para super admins, revisão de acessibilidade e testes de penetração.

## O que está implementado

- Site público: início, escritório, equipe, áreas, conteúdos, FAQ, contatos, páginas legais com aviso de pendência.
- Interface pública no layout original, com ajustes de acessibilidade (skip link, foco visível e menu com `aria-expanded`).
- **Painel administrativo em `/admin`**: visão geral com KPIs, pesquisa global, mensagens/solicitações recentes, casos, documentos recebidos, próximos compromissos e clientes.
- **Painel do advogado em `/advogado`**: central individual com indicadores e acesso de consulta aos casos do escritório; alterações seguem as atribuições e permissões.
- **Menus organizados**: clientes, casos, solicitações, mensagens e relatos, documentos, compromissos, atualizações, conteúdos, FAQ, relatórios, usuários, permissões, segurança, configurações, auditoria, lixeira e contatos. Lixeira e segurança são exclusivas de super admins.
- **Busca administrativa** em `/admin/busca` por cliente, caso, mensagem, documento ou solicitação, respeitando o escopo do usuário.
- **Relatórios** em `/admin/relatorios`, com filtro por período, casos acessíveis, indicadores de status, documentos/mensagens recebidos, produtividade por responsável, tempo médio de resposta e exportação CSV.
- **Cadastro público de clientes** em `/cadastro`, com consentimento, validação, rate limit e login automático.
- **Super administradores**: Edleusa e Rozária têm contas individuais com acesso total a usuários, casos, arquivos, mensagens, relatos internos, contatos e auditoria.
- **Gestão de usuários**: criar, editar nome/e-mail/perfil, ativar/desativar, redefinir senha e definir super admins, com proteção para não desativar o último super admin.
- **Permissões configuráveis**: super admins ajustam permissões individuais de administradores e advogados em `/admin/permissoes`.
- **Clientes por advogado**: advogados podem cadastrar e editar seus próprios clientes em `/admin/clientes`, com telefone, vínculo de responsável, senha inicial e troca obrigatória no primeiro acesso.
- **Configurações**: parâmetros de alerta/notificação em `/admin/configuracoes` (horas para não lidas, horas sem movimentação, antecedência de compromisso).
- **Casos**: criação e edição de casos com cliente, número do processo, área, status, descrição e responsável. O advogado cria/edita os casos atribuídos; o super admin vê e edita todos. Toda alteração é auditada com valores antes/depois.
- **Novo atendimento pelo cliente**: o cliente informa assunto e descrição, o sistema cria o caso com o título original, mensagem inicial e evento de histórico. O caso entra na fila sem responsável e o administrador distribui para um advogado.
- **Renomeação e histórico**: o título original é preservado; renomeações, mudanças de status e atribuições geram eventos em `case_events`, com visibilidade interna ou ao cliente. O cliente tem uma página de detalhe do atendimento com histórico visível, mensagens, documentos, atualizações, compromissos e solicitações.
- **Meu Espaço do cliente**: início simplificado, atendimentos, conversas por assunto, documentos, compromissos, atualizações, pendências e perfil. A abertura de uma conversa atualiza a leitura individual; a tela inicial não marca mensagens como lidas.
- **Pendências do cliente**: o escritório cria solicitações de documentos/informações; o cliente vê o status, envia o arquivo diretamente pela pendência e o escritório registra a análise. Status: Aberta, Recebida, Em análise e Atendida.
- **Status documental**: documentos recebidos entram como “Aguardando análise”; o escritório pode marcá-los como analisado, aceito, complementação ou disponibilizado, com observações de análise. O cliente vê o status, a análise e recebe notificação.
- **Compromissos**: status pendente, realizado ou cancelado; lembretes automáticos com base na antecedência configurada; o cliente vê o status na área dele e recebe notificações.
- **Perfil do cliente**: o cliente pode atualizar nome e telefone; a alteração de e-mail é solicitada à equipe.
- **Arquivos por cliente/caso**: central de arquivos com filtros por cliente, caso e direção (recebido do cliente ou enviado pelo escritório), exibindo quem enviou, revisão e vínculo com o caso. O acesso é isolado por caso para funcionários.
- **Mensagens e relatos**: mensagens ao cliente aparecem na área privada; relatos internos são visíveis apenas para a equipe. O cliente vê **“Suporte do escritório”**, e o advogado escolhe, por mensagem, se quer se identificar. O admin sempre vê o autor real.
- **Status e alertas**: badges coloridos (vermelho para novo/não lido, amarelo em andamento, azul aguardando cliente, verde concluído, cinza informativo), animação discreta para itens antigos e alertas de inatividade configuráveis.
- **Central de notificações**: ícone no cabeçalho com contador, lista de notificações, marcação de leitura, notificações do navegador com autorização e deduplicação. O e-mail depende de SMTP configurado.
- **Portal do cliente**: casos, avisos de atualização, documentos enviados pelo escritório, upload de documentos, solicitações de informação, mensagens com o suporte, compromissos e dados cadastrais.
- Painel administrativo: clientes, usuários, casos, atualizações, compromissos, tarefas/prazos, documentos, documentos internos, solicitações, mensagens ao cliente, relatos internos, contatos, conteúdos, FAQ e auditoria.
- **Escopo de funcionário**: advogados podem consultar todos os casos ativos e documentos vinculados. Alterar casos, responder conversas e realizar outras operações continua sujeito às atribuições e permissões. Contatos gerais sem caso mantêm o escopo dos clientes atribuídos.
- **Senhas**: redefinição pelo administrador com senha temporária e troca obrigatória no próximo acesso; página de troca de senha pelo próprio usuário.
- Persistência local em SQLite e armazenamento privado fora da pasta estática.
- Senhas com scrypt e sal aleatório; parâmetros versionados no hash, com re-hash automático no login quando necessário.
- Sessões em memória com expiração por inatividade e tempo absoluto, limpeza periódica e cookie HttpOnly SameSite Strict (com `Secure` quando configurado).
- Token CSRF em ações autenticadas e token assinado para o formulário público de contato; validação de Origin, honeypot e consentimento de privacidade no contato.
- **Rate limiting** em memória para login (por IP e por e-mail), cadastro de cliente e formulário de contato.
- Validação server-side centralizada de campos, tipos e tamanhos; erros de validação não derrubam a requisição e erros internos não vazam detalhes ao usuário.
- Isolamento por `client_id` no servidor; nomes aleatórios para arquivos; validação de extensão e assinatura; limite por arquivo e **quota de armazenamento por cliente**; limpeza de arquivos órfãos.
- **Verificação antivírus opcional** via ClamAV, configurável por `CLAMSCAN` (desativada por padrão).
- Auditoria com ator, ação, entidade, cliente, caso, IP, navegador e valores antes/depois, cobrindo login, cadastro, usuários, casos, arquivos, mensagens, relatos, respostas, redefinições, atribuições, lixeira/restauração e exclusão definitiva. A página de auditoria tem filtros por ator, entidade, ação e período, além de exportação CSV.
- **Lixeira e exclusão definitiva**: super admins podem mover clientes, casos e documentos para a lixeira, restaurar ou excluir permanentemente. A exclusão definitiva remove também arquivos e registros vinculados, exige confirmação com a palavra `EXCLUIR` e gera registro de auditoria. Clientes e funcionários não veem registros de casos excluídos.
- **Permissões aplicadas**: as permissões individuais controlam criação/edição de casos, mensagens e relatos, documentos/análise, pendências, criação/edição de clientes e relatórios. Super admins mantêm acesso total.
- **MFA para super admins**: em `/admin/seguranca`, o super admin ativa TOTP por app autenticador, confirma com um código, recebe oito códigos de recuperação de uso único (armazenados como hash) e pode regenerá-los ou desativar o MFA com senha + código atual. O login passa a exigir a segunda etapa; outro super admin pode redefinir o MFA de uma conta em `/admin/usuarios`. Os códigos de recuperação são exibidos apenas uma vez.
- **Exportação LGPD**: em “Meu perfil”, o cliente baixa um JSON com seus dados pessoais e o histórico visível; o super admin pode gerar o mesmo arquivo em `/admin/clientes`. A exportação não inclui relatos internos, senhas, hashes de recuperação, IPs ou nomes de arquivos internos de armazenamento. Registros na lixeira são exportados com o campo `deleted_at`, quando existirem.
- Cache com ETag para estáticos, download em streaming, cabeçalhos de segurança (CSP, nosniff, X-Frame-Options, Referrer-Policy, Permissions-Policy) e `Server` sem versão do Python.
- `robots.txt`, `sitemap.xml` e metadados básicos de acessibilidade (skip link, foco visível, menu com `aria-expanded`).

## Como ativar o MFA

1. Entre como super admin e acesse `/admin/seguranca`.
2. Clique em **Iniciar configuração** e adicione a chave exibida ao app autenticador (ou use o link `otpauth://`).
3. Informe o código de 6 dígitos para confirmar.
4. Guarde os oito códigos de recuperação exibidos; eles não serão mostrados novamente.
5. No próximo login, o sistema pedirá o código do app ou um código de recuperação.

Se o acesso for perdido, outro super admin pode redefinir o MFA em `/admin/usuarios`. O MFA é opcional nesta versão; recomenda-se ativá-lo em todas as contas de super admin e depois tornar a exigência obrigatória.

## Configuração por variáveis de ambiente

| Variável | Padrão | Função |
|---|---:|---|
| `HOST` | `0.0.0.0` | Interface de escuta |
| `PORT` | `8080` | Porta |
| `DATABASE_URL` | vazio | `sqlite:///...` local ou `postgresql://...` em produção; quando vazia, usa SQLite |
| `APP_DB` | `private/app.db` | Caminho do SQLite quando `DATABASE_URL` não define outro banco |
| `APP_UPLOADS` | `private/uploads` | Pasta privada de arquivos |
| `PUBLIC_ORIGIN` | vazio | Origem pública para sitemap e validação de contato |
| `EXTRA_ORIGINS` | vazio | Origens extras separadas por vírgula |
| `TRUST_PROXY` | `0` | Confia em `X-Forwarded-For` |
| `COOKIE_SECURE` | `0` | Adiciona `Secure` ao cookie de sessão |
| `SESSION_IDLE` | `1800` | Expiração por inatividade (segundos) |
| `SESSION_TTL` | `43200` | Tempo absoluto de sessão (segundos) |
| `LOGIN_IP_LIMIT` | `10` | Tentativas por IP na janela de login |
| `LOGIN_EMAIL_LIMIT` | `5` | Tentativas por e-mail na janela de login |
| `LOGIN_WINDOW` | `900` | Janela do rate limit de login (segundos) |
| `CONTACT_LIMIT` | `5` | Mensagens por IP na janela de contato |
| `CONTACT_WINDOW` | `900` | Janela do rate limit de contato (segundos) |
| `REGISTER_LIMIT` | `5` | Cadastros por IP na janela de cadastro |
| `REGISTER_WINDOW` | `3600` | Janela do rate limit de cadastro (segundos) |
| `MAX_CLIENT_STORAGE` | `104857600` | Quota de documentos por cliente (bytes) |
| `SCRYPT_N` | `65536` | Custo do scrypt (produção: avaliar `131072`+) |
| `CLAMSCAN` | vazio | Caminho do `clamscan` para verificação de uploads |
| `ACCESS_LOG` | `0` | Habilita log de acesso no stderr |

Em produção atrás de proxy HTTPS, use `COOKIE_SECURE=1`, `TRUST_PROXY=1`, `PUBLIC_ORIGIN` correto e HSTS no proxy.

## Limitações e pendências IMPORTANTES

- **NÃO PUBLICAR NA INTERNET**: não passou por auditoria, testes de penetração ou revisão de conformidade LGPD.
- Sessões, rate limiting e desafios MFA são mantidos em memória; não persistem após reinício e pressupõem um único processo. Para várias instâncias, usar armazenamento compartilhado.
- Não há limite de tentativas distribuído, bloqueio permanente de conta, MFA obrigatório, WebAuthn/chaves físicas, verificação de e-mail, e-mail de recuperação, política de retenção, backup automatizado, criptografia de dados em repouso, HTTPS ou gerenciamento robusto de segredos.
- O formulário de contato cria uma conversa de visitante e permite resposta pelo painel; não envia e-mails automaticamente. Não enviar dados sensíveis. O link de acompanhamento é pessoal e expira em 30 dias.
- Conteúdos podem ser criados; o FAQ possui categorias, ordem, edição e publicação/despublicação. A exclusão de conteúdos e FAQ ainda não está exposta.
- Perfis atuais: super admin, administrador, advogado, funcionário e cliente. Advogado e funcionário compartilham `role='staff'` e são diferenciados por `staff_kind`. O advogado pode consultar todos os casos ativos; o funcionário fica restrito aos clientes/casos atribuídos. Ações de alteração seguem atribuições e permissões. Permissões por documento específico e exceções de sigilo por caso continuam pendentes.
- O super admin vê todos os casos por definição. Se houver caso que Edleusa/Rozária não devam acessar, será necessário implementar uma regra de exceção específica.
- As mensagens migradas mantêm o histórico de leitura antigo, que era compartilhado pela equipe; não é possível recuperar quem leu individualmente antes da migração. A leitura individual passa a ser registrada nas conversas após a migração.
- As notificações do navegador exigem permissão do usuário e funcionam apenas com o site aberto; não há envio por e-mail enquanto o SMTP não for configurado. Alertas de inatividade e lembretes de compromissos (1 hora ou 1 dia antes) são gerados durante a consulta periódica de notificações. Não há envio automático por WhatsApp nem sincronização com o calendário do celular.
- O status documental e o de compromissos já funcionam, mas não há upload de nova versão vinculado automaticamente a um documento com “complementação”; o cliente envia um novo arquivo pela área de documentos ou por uma pendência.
- Tarefas e documentos internos já têm edição, remoção lógica e histórico de auditoria na interface, mas ainda não há restauração desses registros pela lixeira, exclusão definitiva de documentos internos, controle de versões de arquivos ou anexos múltiplos por mensagem.
- O cadastro de cliente é auto-aprovado e não exige verificação de e-mail; o administrador pode desativar contas. O perfil mostra os dados, mas alterações cadastrais são solicitadas por mensagem.
- A auditoria é registrada em tabela local e não possui encadeamento de hash/immutabilidade criptográfica; para produção, avaliar trilha append-only externa.
- Endereços e telefones são os que constam nos materiais; validar antes da publicação. Horário de atendimento, redes sociais e canais institucionais oficiais pendentes.
- Os retratos da equipe e as imagens de ambiente foram recortados e otimizados a partir das peças institucionais fornecidas (`static/img/portrait_*.webp`, `founders_portrait.webp`, `office_*.webp` e `emblem.webp`). A imagem dos fundadores é compartilhada porque o material disponível os apresenta juntos. Ainda é recomendável obter fotografias originais individuais sem texto e com autorização de uso. **Não foi realizada edição facial**.
- Os textos legais são placeholders e precisam de elaboração e revisão jurídica. O checkbox de consentimento do contato/cadastro não substitui a política de privacidade.
- Ausência de automação de consulta judicial é intencional.
- Sem integrações pagas, sem contratação de serviços e sem hospedagem configurada.
- A aplicação agora é servida por Flask, mas a lógica continua centralizada em `app.py` e o HTML ainda é gerado por strings (sem templates Jinja2). A separação em módulos e templates segue recomendada antes de evoluir o produto.
- A verificação antivírus só ocorre se `CLAMSCAN` estiver configurado; caso contrário, os uploads passam apenas por validação de tipo/assinatura.
- Paginação foi implementada para auditoria e contatos; listas do painel ainda usam limites fixos.
- A lixeira e a exclusão definitiva já funcionam, mas não há política automática de retenção, anonimização programada ou restauração de backups pela interface. A exclusão definitiva é imediata e irreversível.
- O MFA TOTP está implementado para super admins, mas é opcional; o segredo TOTP fica armazenado no SQLite local, não há QR code embutido (a chave é exibida para entrada manual ou link `otpauth://`) nem WebAuthn/chaves físicas. A exportação LGPD está disponível, mas ainda faltam anonimização, política de retenção, verificação de e-mail, SMTP e criptografia em repouso.
- As permissões são aplicadas nas rotas principais, mas a cobertura deve ser revisada rota a rota antes de produção, especialmente em páginas somente de leitura e ações administrativas menos usadas.

## Arquitetura

`app.py`: núcleo com rotas, regras de acesso, HTML e persistência; `flask_app.py`: adaptador Flask/WSGI que preserva o Handler existente; `wsgi.py`: ponto de entrada WSGI; `db_compat.py`: camada SQLite/PostgreSQL; `create_admin.py`: bootstrap de super administrador; `static/`: CSS, JS e imagens; `private/`: banco, uploads e backups locais (não distribuir com dados reais); `local_only/`: suíte `unittest`, referências visuais, scripts de desenvolvimento e migração SQLite para PostgreSQL (ignorado pelo Git). Tabelas: users, cases, case_assignments, case_events, updates, appointments, appointment_participants, tasks, task_collaborators, task_subtasks, internal_documents, requests, documents, conversations, messages, message_reads, message_attachments, message_mentions, guest_sessions, guest_messages, pendencies, posts, faqs, contacts, audit, assignments, permissions, settings, notifications, team_chat_messages, team_chat_mentions, team_chat_reads, schema_migrations.

## Antes de implantar

1. Revisão de segurança, LGPD, controles de acesso e modelagem de dados por profissional responsável.
2. Migrar para stack de produção com servidor web robusto, HTTPS, sessões persistentes seguras, rate limiting compartilhado, MFA obrigatório/WebAuthn para super admins, recuperação de senha por e-mail, monitoramento, verificação antivírus e auditoria completa.
3. Revisar a política de acesso global aos casos, notificações por e-mail, edição/exclusão de conteúdos e documentos, política de privacidade e consentimentos.
4. Avaliar armazenamento privado e backups PostgreSQL criptografados, com retenção e restauração testada; considerar trilha de auditoria append-only/hash chain.
5. Testar com dados fictícios e validar conteúdo institucional e imagens com a equipe.

## Custos

Execução local: sem contratação e sem mensalidade. Hospedagem pública, domínio, e-mail transacional, backups e armazenamento de produção dependem de decisões posteriores; nenhuma conta ou assinatura foi criada.
