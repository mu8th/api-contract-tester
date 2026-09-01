const app = document.getElementById('app');


function load_specs() {
    fetch('/api/specs')
        .then(response => response.json())
        .then(data => {
            const ul = document.getElementById('specs-list');
            data.forEach(spec => {
                const li = document.createElement('li');
                li.textContent = `${spec.name} (${spec.version})`;
                ul.appendChild(li);
            });
        })
}


function load_tests() {
    fetch('/api/tests')
        .then(response => response.json())
        .then(data => {
            const tbody = document.querySelector('#tests-table tbody');
            data.forEach(test => {
                const tr = document.createElement('tr');
                tr.innerHTML = `<td>${test.id}</td><td>${test.status}</td><td>${test.drift_score}</td>`;
                tbody.appendChild(tr);
            });
        })
}


function load_diffs() {
    fetch('/api/results')
        .then(response => response.json())
        .then(data => {
            const container = document.getElementById('diffs-container');
            data.forEach(result => {
                const div = document.createElement('div');
                div.textContent = `Drift: ${result.drift_score} | Violations: ${result.violations.length}`;
                container.appendChild(div);
            });
        })
}


load_specs()
load_tests()
load_diffs()