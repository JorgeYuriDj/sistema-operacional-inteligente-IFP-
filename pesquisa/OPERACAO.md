# Operação da Pesquisa IFP

## Entrada e dados

A pesquisa pública está em `/`; a administração em `/admin`. Credenciais são entregues
em arquivo privado ao responsável. Não estão neste repositório. A administração permite
ler e exportar; não oferece remoção em massa ou alteração silenciosa de respostas.

Não publicar a base, backups ou arquivos de configuração. Exportações contêm dados
pessoais: guardar em local privado e usar contatos apenas quando a autorização permitir.
A coleta é voluntária e não garante uma amostra representativa ou pessoas únicas.

## Configuração

Copiar os nomes de `.env.example` para o gerenciador de configuração do ambiente.
Gerar segredos aleatórios e uma chave Fernet. O serviço recusa inicialização sem chave
válida. Definir origem e host canônicos, HTTPS e proxy confiável. Nunca habilitar confiança
de proxy quando o servidor puder ser acessado diretamente por clientes.

Instalar `requirements.lock`. Em produção, usar a imagem de `Dockerfile` e o volume
persistente definido em `compose.yml`. O contêiner não roda como root, não publica
porta direta e possui limites de memória, CPU e processos. O proxy precisa substituir
os cabeçalhos de encaminhamento e limitar o corpo a 16 KiB.

## Backup e restauração

O diretório persistente mantém banco e registro de exclusões. A configuração guarda
a chave de criptografia separadamente; perder essa chave impede a leitura das respostas
abertas e dos contatos. Uma cópia deve permanecer com o responsável.

`python manage.py backup --destination /backups` cria snapshot online, verifica
integridade e retém snapshots por até 30 dias. Isso não exclui respostas do banco ativo.
`python manage.py check` verifica integridade e mostra somente contagens.

Uma restauração exige origem, destino **novo** e registro **atual** de exclusões:

```sh
python manage.py restore --source /backups/snapshot.sqlite3 --destination /data/restored.sqlite3 --erasures /data/erasures.jsonl
```

O comando não sobrescreve o banco ativo e revoga as sessões na cópia restaurada. Antes
de apontar o serviço à cópia, verificar integridade, contagem e leitura de uma resposta
com a chave correta. Parar a aplicação durante a troca, preservar o banco anterior
para rollback e reaplicar as solicitações de exclusão mais recentes.

Snapshots no mesmo servidor protegem contra erro lógico, mas não contra perda da VPS.
Manter cópia adicional fora dela, com acesso restrito, incluindo o registro de exclusões.
Nunca copiar só o arquivo principal do banco ativo durante uso de WAL: usar o backup.

## Solicitação de exclusão

Confirmar o pedido do titular pelo canal do IFP e localizar o protocolo. Executar:

```sh
python manage.py erase --id PROTOCOLO --confirm-id PROTOCOLO
```

O registro é removido do banco ativo e seu identificador entra no registro de exclusões.
Backups históricos podem conter o dado até expirar; o procedimento de restauração
reaplica as exclusões. Não contatar quem recusou a autorização de contato promocional.

## Atualização e recuperação de acesso

Cada release usa uma imagem distinta e o mesmo volume de dados. Fazer backup antes
de trocar; verificar `/healthz`, login, contagem e formulário depois. Para rollback de
código, selecionar a imagem anterior preservando o volume. Migrações futuras precisam
ser aditivas ou ter plano específico de reversão.

Para recuperar acesso, um operador autorizado deve gerar novo hash de senha e novo
segredo TOTP, atualizar apenas a conta pretendida e apagar suas sessões. Nunca enviar
senhas por logs ou incluir credenciais em comandos versionados.

## Limites operacionais

Há proteção de frequência por conexão e conta, sem garantia contra ataques distribuídos.
Monitorar disponibilidade, espaço, sucesso dos backups e renovação de HTTPS. O IFP deve
revisar a necessidade de retenção e as permissões de acesso periodicamente. Revisão técnica
e testes documentados não equivalem a certificação ou auditoria jurídica independente.
