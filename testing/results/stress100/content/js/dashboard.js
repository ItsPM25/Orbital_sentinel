/*
   Licensed to the Apache Software Foundation (ASF) under one or more
   contributor license agreements.  See the NOTICE file distributed with
   this work for additional information regarding copyright ownership.
   The ASF licenses this file to You under the Apache License, Version 2.0
   (the "License"); you may not use this file except in compliance with
   the License.  You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
*/
var showControllersOnly = false;
var seriesFilter = "";
var filtersOnlySampleSeries = true;

/*
 * Add header in statistics table to group metrics by category
 * format
 *
 */
function summaryTableHeader(header) {
    var newRow = header.insertRow(-1);
    newRow.className = "tablesorter-no-sort";
    var cell = document.createElement('th');
    cell.setAttribute("data-sorter", false);
    cell.colSpan = 1;
    cell.innerHTML = "Requests";
    newRow.appendChild(cell);

    cell = document.createElement('th');
    cell.setAttribute("data-sorter", false);
    cell.colSpan = 3;
    cell.innerHTML = "Executions";
    newRow.appendChild(cell);

    cell = document.createElement('th');
    cell.setAttribute("data-sorter", false);
    cell.colSpan = 7;
    cell.innerHTML = "Response Times (ms)";
    newRow.appendChild(cell);

    cell = document.createElement('th');
    cell.setAttribute("data-sorter", false);
    cell.colSpan = 1;
    cell.innerHTML = "Throughput";
    newRow.appendChild(cell);

    cell = document.createElement('th');
    cell.setAttribute("data-sorter", false);
    cell.colSpan = 2;
    cell.innerHTML = "Network (KB/sec)";
    newRow.appendChild(cell);
}

/*
 * Populates the table identified by id parameter with the specified data and
 * format
 *
 */
function createTable(table, info, formatter, defaultSorts, seriesIndex, headerCreator) {
    var tableRef = table[0];

    // Create header and populate it with data.titles array
    var header = tableRef.createTHead();

    // Call callback is available
    if(headerCreator) {
        headerCreator(header);
    }

    var newRow = header.insertRow(-1);
    for (var index = 0; index < info.titles.length; index++) {
        var cell = document.createElement('th');
        cell.innerHTML = info.titles[index];
        newRow.appendChild(cell);
    }

    var tBody;

    // Create overall body if defined
    if(info.overall){
        tBody = document.createElement('tbody');
        tBody.className = "tablesorter-no-sort";
        tableRef.appendChild(tBody);
        var newRow = tBody.insertRow(-1);
        var data = info.overall.data;
        for(var index=0;index < data.length; index++){
            var cell = newRow.insertCell(-1);
            cell.innerHTML = formatter ? formatter(index, data[index]): data[index];
        }
    }

    // Create regular body
    tBody = document.createElement('tbody');
    tableRef.appendChild(tBody);

    var regexp;
    if(seriesFilter) {
        regexp = new RegExp(seriesFilter, 'i');
    }
    // Populate body with data.items array
    for(var index=0; index < info.items.length; index++){
        var item = info.items[index];
        if((!regexp || filtersOnlySampleSeries && !info.supportsControllersDiscrimination || regexp.test(item.data[seriesIndex]))
                &&
                (!showControllersOnly || !info.supportsControllersDiscrimination || item.isController)){
            if(item.data.length > 0) {
                var newRow = tBody.insertRow(-1);
                for(var col=0; col < item.data.length; col++){
                    var cell = newRow.insertCell(-1);
                    cell.innerHTML = formatter ? formatter(col, item.data[col]) : item.data[col];
                }
            }
        }
    }

    // Add support of columns sort
    table.tablesorter({sortList : defaultSorts});
}

$(document).ready(function() {

    // Customize table sorter default options
    $.extend( $.tablesorter.defaults, {
        theme: 'blue',
        cssInfoBlock: "tablesorter-no-sort",
        widthFixed: true,
        widgets: ['zebra']
    });

    var data = {"OkPercent": 16.6, "KoPercent": 83.4};
    var dataset = [
        {
            "label" : "FAIL",
            "data" : data.KoPercent,
            "color" : "#FF6347"
        },
        {
            "label" : "PASS",
            "data" : data.OkPercent,
            "color" : "#9ACD32"
        }];
    $.plot($("#flot-requests-summary"), dataset, {
        series : {
            pie : {
                show : true,
                radius : 1,
                label : {
                    show : true,
                    radius : 3 / 4,
                    formatter : function(label, series) {
                        return '<div style="font-size:8pt;text-align:center;padding:2px;color:white;">'
                            + label
                            + '<br/>'
                            + Math.round10(series.percent, -2)
                            + '%</div>';
                    },
                    background : {
                        opacity : 0.5,
                        color : '#000'
                    }
                }
            }
        },
        legend : {
            show : true
        }
    });

    // Creates APDEX table
    createTable($("#apdexTable"), {"supportsControllersDiscrimination": true, "overall": {"data": [0.09071428571428572, 500, 1500, "Total"], "isController": false}, "titles": ["Apdex", "T (Toleration threshold)", "F (Frustration threshold)", "Label"], "items": [{"data": [0.109, 500, 1500, "GET /api/satellites"], "isController": false}, {"data": [0.114, 500, 1500, "POST /api/alerts/:id/acknowledge"], "isController": false}, {"data": [0.083, 500, 1500, "GET /api/satellites/:id/telemetry"], "isController": false}, {"data": [0.086, 500, 1500, "GET /api/tle"], "isController": false}, {"data": [0.026, 500, 1500, "POST /api/login"], "isController": false}, {"data": [0.1, 500, 1500, "GET /api/ranking"], "isController": false}, {"data": [0.117, 500, 1500, "GET /api/alerts"], "isController": false}]}, function(index, item){
        switch(index){
            case 0:
                item = item.toFixed(3);
                break;
            case 1:
            case 2:
                item = formatDuration(item);
                break;
        }
        return item;
    }, [[0, 0]], 3);

    // Create statistics table
    createTable($("#statisticsTable"), {"supportsControllersDiscrimination": true, "overall": {"data": ["Total", 3500, 2919, 83.4, 25240.413142857116, 14, 30613, 30021.0, 30104.0, 30145.0, 30407.92, 3.2403026998202096, 1.613502581479726, 0.7055686800673242], "isController": false}, "titles": ["Label", "#Samples", "FAIL", "Error %", "Average", "Min", "Max", "Median", "90th pct", "95th pct", "99th pct", "Transactions/s", "Received", "Sent"], "items": [{"data": ["GET /api/satellites", 500, 422, 84.4, 25465.28400000001, 17, 30513, 30021.0, 30095.0, 30139.9, 30298.84, 0.5051500042937751, 0.15334854466283765, 0.10118786023509682], "isController": false}, {"data": ["POST /api/alerts/:id/acknowledge", 500, 415, 83.0, 25073.138, 19, 30314, 30019.0, 30095.0, 30128.9, 30260.98, 0.5209272087574115, 0.12148897503143796, 0.12266207868709673], "isController": false}, {"data": ["GET /api/satellites/:id/telemetry", 500, 431, 86.2, 26037.884, 53, 30603, 30023.0, 30113.0, 30196.7, 30471.95, 0.47628800182894593, 0.6654831778054554, 0.10936019041994312], "isController": false}, {"data": ["GET /api/tle", 500, 437, 87.4, 26363.184000000016, 14, 30596, 30023.0, 30113.0, 30166.9, 30509.69, 0.4630873104815182, 0.15598354390299246, 0.08959654096933435], "isController": false}, {"data": ["POST /api/login", 500, 386, 77.2, 23691.060000000005, 257, 30613, 30017.0, 30094.0, 30121.95, 30232.92, 0.5555012398787673, 0.1302715505317258, 0.15086198516145088], "isController": false}, {"data": ["GET /api/ranking", 500, 426, 85.2, 25721.33999999998, 18, 30611, 30021.0, 30117.8, 30178.0, 30503.16, 0.49029702193588875, 0.15018123369762404, 0.09677620515007992], "isController": false}, {"data": ["GET /api/alerts", 500, 402, 80.4, 24331.00200000001, 17, 30580, 30019.0, 30094.0, 30118.0, 30249.95, 0.5377309688944144, 0.36241386894205735, 0.10561372310941858], "isController": false}]}, function(index, item){
        switch(index){
            // Errors pct
            case 3:
                item = item.toFixed(2) + '%';
                break;
            // Mean
            case 4:
            // Mean
            case 7:
            // Median
            case 8:
            // Percentile 1
            case 9:
            // Percentile 2
            case 10:
            // Percentile 3
            case 11:
            // Throughput
            case 12:
            // Kbytes/s
            case 13:
            // Sent Kbytes/s
                item = item.toFixed(2);
                break;
        }
        return item;
    }, [[0, 0]], 0, summaryTableHeader);

    // Create error table
    createTable($("#errorsTable"), {"supportsControllersDiscrimination": false, "titles": ["Type of error", "Number of errors", "% in errors", "% in all samples"], "items": [{"data": ["500/Internal Server Error", 2919, 100.0, 83.4], "isController": false}]}, function(index, item){
        switch(index){
            case 2:
            case 3:
                item = item.toFixed(2) + '%';
                break;
        }
        return item;
    }, [[1, 1]]);

        // Create top5 errors by sampler
    createTable($("#top5ErrorsBySamplerTable"), {"supportsControllersDiscrimination": false, "overall": {"data": ["Total", 3500, 2919, "500/Internal Server Error", 2919, "", "", "", "", "", "", "", ""], "isController": false}, "titles": ["Sample", "#Samples", "#Errors", "Error", "#Errors", "Error", "#Errors", "Error", "#Errors", "Error", "#Errors", "Error", "#Errors"], "items": [{"data": ["GET /api/satellites", 500, 422, "500/Internal Server Error", 422, "", "", "", "", "", "", "", ""], "isController": false}, {"data": ["POST /api/alerts/:id/acknowledge", 500, 415, "500/Internal Server Error", 415, "", "", "", "", "", "", "", ""], "isController": false}, {"data": ["GET /api/satellites/:id/telemetry", 500, 431, "500/Internal Server Error", 431, "", "", "", "", "", "", "", ""], "isController": false}, {"data": ["GET /api/tle", 500, 437, "500/Internal Server Error", 437, "", "", "", "", "", "", "", ""], "isController": false}, {"data": ["POST /api/login", 500, 386, "500/Internal Server Error", 386, "", "", "", "", "", "", "", ""], "isController": false}, {"data": ["GET /api/ranking", 500, 426, "500/Internal Server Error", 426, "", "", "", "", "", "", "", ""], "isController": false}, {"data": ["GET /api/alerts", 500, 402, "500/Internal Server Error", 402, "", "", "", "", "", "", "", ""], "isController": false}]}, function(index, item){
        return item;
    }, [[0, 0]], 0);

});
