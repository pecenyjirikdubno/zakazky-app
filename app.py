from flask import Flask, render_template, request, redirect, url_for, flash
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Neplatné přihlašovací údaje')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ------------------ DASHBOARD ------------------
@app.route('/')
@login_required
def dashboard():
    projects = Project.query.all()
    return render_template('dashboard.html', projects=projects, user=current_user)

# ------------------ PROJECT ------------------
@app.route('/project/<int:project_id>', methods=['GET', 'POST'])
@login_required
def project_page(project_id):
    project = Project.query.get_or_404(project_id)
    if request.method == 'POST':
        if current_user.role == 'admin':
            if 'close_project' in request.form:
                project.closed = True
                db.session.commit()
            elif 'export_excel' in request.form:
                entries = Entry.query.filter_by(project_id=project.id).all()
                data = [{
                    'Date': e.date,
                    'Material Code': e.material_code,
                    'Document Number': e.document_number,
                    'Supplier': e.supplier,
                    'Quantity': e.quantity,
                    'Description': e.description,
                    'Hours Worked': e.hours_worked,
                    'KM': e.km,
                    'Travel Time': e.travel_time
                } for e in entries]
                df = pd.DataFrame(data)
                df.to_excel(f'{project.name}.xlsx', index=False)
                flash('Export dokončen')
    entries = Entry.query.filter_by(project_id=project.id).all()
    return render_template('project.html', project=project, entries=entries, user=current_user)

# ------------------ SPUŠTĚNÍ ------------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Přidání default admina, pokud neexistuje
        if not User.query.filter_by(username='admin').first():
            admin_user = User(username='admin', password='admin123', role='admin')
            db.session.add(admin_user)
            db.session.commit()
    app.run(debug=True)
