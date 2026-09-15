# Pesquisa IFP

Pesquisa pública para estudantes e estagiários de Educação Física, com administração
privada e histórico cumulativo. As planilhas de planejamento existentes foram preservadas.

## Aplicativo

- [Pesquisa pública](https://institutofacilitypro-bb4df8ce.nip.io/)
- [Administração](https://institutofacilitypro-bb4df8ce.nip.io/admin)

Endereço temporário com HTTPS. O endereço anterior encaminha para este; a adoção
do domínio próprio depende da configuração de DNS pelo responsável.

O código está em `pesquisa/`. A página pública apresenta o Instituto Facility PRO e
as cinco perguntas da pesquisa, uma por etapa, com retorno sem perder o que foi
preenchido. A sexta etapa reúne identificação e consentimentos. Nome, e-mail e
telefone são opcionais. A autorização para contato é independente da participação.

O painel `/admin` exige senha e código de autenticador. Mostra contagens, gráficos,
evolução diária, cruzamento formação × formato, respostas completas e exportação CSV.
Filtros: período, formação, área e formato. Cada percentual indica sua base; a pergunta
de múltipla seleção pode somar mais de 100%. Os insights são cálculos determinísticos,
sem serviço de IA e sem custo de inferência.

## Identidade visual

Logo oficial em `pesquisa/static/ifp-logo.png`, preservada sem recorte, recoloração ou
recriação. A mesma arte aparece no formulário, login e painel, com proporção original.
Paleta IFP: preto quente `#0C0A09`, dourado `#D4AF37` e creme `#F5F2EA`, com os tons
de superfície e texto definidos pela Plataforma IFP. A leitura usa fundo creme,
texto escuro e a fonte Hanken Grotesk hospedada no próprio site, sem requisições
a serviços de fontes. A licença OFL acompanha os arquivos em `static/fonts/`.

No celular, a apresentação é curta e o formulário vem antes do contexto institucional
detalhado. Campos têm rótulos visíveis, alternativas com área de toque ampla e
tamanho de texto de pelo menos 16 px nos controles. A navegação respeita a
preferência do sistema por movimento reduzido.

## Persistência e segurança

- SQLite em volume persistente, transações, restrições e migração aditiva versionada.
- Repetir o mesmo envio depois de falha de conexão não cria outra resposta.
- Não há garantia de pessoas únicas: um novo formulário pode gerar outro envio.
- Resposta aberta, nome e contatos cifrados no banco; chaves fora do código e do banco.
- Sessões administrativas revogáveis, expiração absoluta, senha com scrypt e TOTP.
- CSRF, validação no servidor, limite de corpo e tentativas, CSP e cookies seguros.
- API de leitura e exportações acessíveis somente após autenticação.
- Exportação neutraliza fórmulas de planilha inseridas em respostas.
- Backup usa snapshot consistente, com verificação de integridade e retenção de 30 dias.
- Exclusão solicitada pelo titular fica registrada para ser reaplicada em restaurações.

Veja [operação](pesquisa/OPERACAO.md) e [verificação](pesquisa/VERIFICACAO.md).
