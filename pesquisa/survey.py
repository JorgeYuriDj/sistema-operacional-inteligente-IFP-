"""Versão imutável das perguntas e códigos do questionário."""
VERSION = "estudantes-2026-09-v1"
PRIVACY_VERSION = "2026-09-15-v1"
CONTACT_URL = "https://wa.me/5561981337910"
QUESTIONS = [
    {"id": "stage", "title": "Em qual momento da sua formação você está?", "options": [
        ("s12", "1º ou 2º semestre"), ("s34", "3º ou 4º semestre"),
        ("s56", "5º ou 6º semestre"), ("s78", "7º ou 8º semestre"),
        ("graduate", "Já concluí a graduação")]},
    {"id": "area", "title": "Em qual área você mais deseja atuar profissionalmente?", "options": [
        ("gym", "Academia / musculação"), ("group", "Ginástica coletiva / aulas em grupo"),
        ("personal", "Personal Trainer"), ("sport", "Esporte / treinamento esportivo"),
        ("health", "Saúde / qualidade de vida"), ("management", "Gestão de academias e negócios fitness"),
        ("unsure", "Ainda não sei")]},
    {"id": "gaps", "title": "Em quais aspectos você se sente menos preparado para entrar no mercado de trabalho?", "multiple": True, "options": [
        ("training", "Prescrição e aplicação prática do treinamento"), ("classes", "Condução de aulas coletivas"),
        ("service", "Atendimento e relacionamento com alunos"), ("communication", "Comunicação e postura profissional"),
        ("sales", "Vendas e captação de alunos"), ("leadership", "Gestão e liderança"),
        ("business", "Empreendedorismo"), ("all", "Ainda não me sinto preparado em nenhuma dessas áreas")]},
    {"id": "format", "title": "Qual formato de desenvolvimento profissional mais despertaria seu interesse?", "options": [
        ("short", "Cursos práticos de curta duração"), ("workshops", "Workshops presenciais"),
        ("events", "Palestras e eventos"), ("mentoring", "Mentoria com profissionais experientes"),
        ("complete", "Formação profissional mais completa"), ("online", "Conteúdos online / aulas gravadas"),
        ("combined", "Programa que combine diferentes formatos")]},
    {"id": "wish", "title": "Se o IFP pudesse resolver UMA dificuldade da sua formação e preparação para o mercado de trabalho, qual você gostaria que fosse?"},
]
LABELS = {q["id"]: dict(q.get("options", [])) for q in QUESTIONS}
