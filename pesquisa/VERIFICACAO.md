# Verificação — 15/09/2026

## Resultado executado

- 34 testes de API, autenticação, autorização, validação, persistência e backup passaram.
- 2 testes completos de navegador passaram: Chromium/Chrome com perfil Pixel 7 e
  WebKit com perfil iPhone 13, além das visualizações de computador.
- Os mesmos 36 testes também passaram no GitHub/Ubuntu em 54,66 segundos, seguidos
  de auditoria das dependências e construção Docker. [Execução verificada](https://github.com/JorgeYuriDj/sistema-operacional-inteligente-IFP-/actions/runs/35027389691).
- Auditoria de `requirements.lock`: nenhuma vulnerabilidade conhecida no catálogo
  consultado nesta data. Isso não prova ausência de falhas desconhecidas.
- JavaScript validado e nenhuma exceção de execução ou violação de CSP observada nos
  fluxos de navegador. Revisão visual das páginas no computador e no celular realizada.

## Cenários cobertos

Questionário completo; campos pessoais opcionais; consentimento independente; máximo
de duas alternativas e exclusividade de “nenhuma dessas áreas”; rejeição de payload
adulterado; limites de tamanho; CSRF; origem e host; tentativas de acesso sem login;
senha e TOTP; replay de código; expiração e revogação de sessão; limitação persistente
de tentativas; XSS exibido como texto; fórmulas neutralizadas no CSV; percentuais,
empates, filtros, datas em Brasília, paginação e estado vazio.

Também foram executados envio repetido e concorrente do mesmo protocolo, falha de
conexão com nova tentativa, reinício do processo com consulta aos registros anteriores,
migração repetida sem perda, restrições SQL, integridade e restauração com exclusões
reaplicadas. O campo de contato não é usado como chave única de pessoa.

Em cada execução de navegador, 30 envios sintéticos por HTTP, com concorrência 12,
foram gravados sem perda, somando 32 registros no banco isolado. Medidas locais da
última rodada local: p95 de 556 ms no ensaio Chromium e 485 ms no ensaio WebKit. Não são
estimativa de capacidade máxima nem medição de latência da internet em celulares.

## VPS e HTTPS

Verificação adicional no endereço publicado, com certificado validado:

- Envio e confirmação usando os perfis Android e iPhone.
- Login real com senha e autenticador, filtros e download CSV.
- Após a correção de compatibilidade, o CSV filtrado foi baixado novamente em
  Chrome e WebKit no endereço HTTPS, preservando a página do painel aberta.
- Reinício do contêiner e confirmação de que os registros e o acesso persistiram.
- Backup do banco em uso, integridade e restauração de uma cópia com os dois protocolos
  técnicos excluídos. Registro de exclusões reaplicado e zero respostas restauradas.
- Os dois envios de verificação foram excluídos pelo procedimento de operação.
  Ao finalizar a verificação, a pesquisa real tinha **zero respostas**.
- Contêiner sem root, sistema de arquivos de aplicação somente leitura, sem porta
  direta publicada e rede própria. A rota HTTPS foi acrescentada com recarga do proxy,
  sem reiniciar o processo; respostas anteriores de outros serviços permaneceram iguais.
- Backup diário na VPS ativado e executado. Cópia adicional no computador verificada
  e programada para execução diária quando a sessão do responsável estiver disponível.

## Falhas encontradas e corrigidas durante a construção

1. Duração do CSRF configurada com tipo incompatível: alterada para segundos e
   novamente testada com submissões e login reais.
2. Versão inicial de dependência de criptografia com alertas conhecidos: atualizada,
   travada na lista de dependências e auditada novamente.
3. Política `no-referrer` causava `Origin: null` no POST nativo do login: política
   ajustada para `same-origin`, mantendo bloqueio de origem externa e proteção CSRF.
4. Teste tentava forçar uma terceira caixa marcada apesar da recusa esperada:
   instrumento corrigido para clicar e verificar a recusa, preservando o limite.
5. Executor auxiliar era coletado como teste: adicionada guarda de execução direta.
6. Espaço entre palavras se perdia em quebra de título no celular: texto corrigido.
7. No primeiro teste em Linux, WebKit não gerava o evento esperado ao exportar CSV.
   O link recebeu o atributo HTML `download`, mantendo autenticação, filtros e o
   cabeçalho de anexo. O download e todo o fluxo passaram novamente em ambos os
   navegadores, tanto no Windows quanto no Linux; nenhum teste foi desativado.

## Reproduzir

```sh
pip install -r requirements-dev.txt -c requirements.lock
python -m playwright install --with-deps chromium webkit chrome
python -m pytest tests -q --tb=short
python -m pip_audit -r requirements.lock --progress-spinner off
```

Os testes criam bancos e identidades sintéticas temporárias; não usam credenciais de
produção. A porta local 8791 deve estar livre. Capturas e resumos de execução ficam em
`artifacts/`, fora do Git. A automação no GitHub repete os testes sem credenciais.

## Limites

Perfis móveis simulam dimensões, interação por toque e agente de navegador. Os testes
WebKit não foram executados em um iPhone físico; Chromium não foi executado em aparelho
Android físico. Navegadores internos de Instagram e WhatsApp não foram inspecionados.
Não houve teste de capacidade máxima, ataque distribuído, auditoria externa ou
certificação de conformidade jurídica. Backups futuros exigem acompanhamento operacional;
a execução atual não comprova todas as futuras. A cópia no computador depende dele
estar disponível; o backup na VPS é independente dessa disponibilidade.
